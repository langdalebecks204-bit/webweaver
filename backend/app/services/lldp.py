import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device
from app.services.oui import normalize_mac
from app.services.snmp import (
    OID_IF_DESCR,
    OID_IF_NAME,
    OID_LLDP_LOC_PORT_DESC,
    OID_LLDP_LOC_PORT_ID,
    OID_LLDP_REM_CHASSIS_ID,
    OID_LLDP_REM_MAN_ADDR,
    OID_LLDP_REM_PORT_DESC,
    OID_LLDP_REM_PORT_ID,
    OID_LLDP_REM_SYS_NAME,
    snmp_walk,
)


def _decode_bytes_str(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""
    elif isinstance(val, str):
        return val.strip()
    return str(val) if val is not None else ""


def _format_chassis_id(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        if len(val) == 6:
            return ":".join(f"{b:02X}" for b in val)
        text = _decode_bytes_str(val)
        norm = normalize_mac(text)
        return norm if norm else text
    elif isinstance(val, str):
        norm = normalize_mac(val)
        return norm if norm else val.strip()
    return ""


def parse_lldp_rem_table(
    rem_chassis: Dict[str, Any],
    rem_ports: Dict[str, Any],
    rem_sysnames: Dict[str, Any],
    rem_man_addrs: Optional[Dict[str, Any]] = None,
    loc_ports: Optional[Dict[int, str]] = None,
) -> List[Dict[str, Any]]:
    """Parse raw SNMP walk dictionaries from LLDP-MIB into neighbor entries."""
    loc_ports = loc_ports or {}
    rem_man_addrs = rem_man_addrs or {}

    # Pre-parse management IP table: key (locPortNum, remIndex) -> IP
    man_ips: Dict[tuple, str] = {}
    for oid in rem_man_addrs.keys():
        parts = oid.strip(".").split(".")
        # ... .locPortNum.remIndex.subtype.len.ip1.ip2.ip3.ip4 (at least 6 suffix parts)
        if len(parts) >= 6:
            ip_candidate = ".".join(parts[-4:])
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_candidate):
                try:
                    # locate locPortNum and remIndex
                    # Usually: [prefix] .timeMark.locPortNum.remIndex.subtype.len.ip1.ip2.ip3.ip4
                    loc_p = int(parts[-7])
                    rem_i = int(parts[-6])
                    man_ips[(loc_p, rem_i)] = ip_candidate
                except Exception:
                    pass

    neighbors: List[Dict[str, Any]] = []

    # Map by (locPortNum, remIndex)
    for oid, chassis_val in rem_chassis.items():
        parts = oid.strip(".").split(".")
        if len(parts) < 3:
            continue
        try:
            loc_port_num = int(parts[-2])
            rem_index = int(parts[-1])
        except Exception:
            continue

        chassis_str = _format_chassis_id(chassis_val)

        # Find matching port id
        port_oid = f"{OID_LLDP_REM_PORT_ID}.{parts[-3]}.{loc_port_num}.{rem_index}"
        port_val = rem_ports.get(port_oid)
        if port_val is None:
            # Try finding any oid ending with locPortNum.remIndex
            for k, v in rem_ports.items():
                if k.endswith(f".{loc_port_num}.{rem_index}"):
                    port_val = v
                    break
        port_id_str = _decode_bytes_str(port_val)

        # Find matching sysname
        sys_val = None
        for k, v in rem_sysnames.items():
            if k.endswith(f".{loc_port_num}.{rem_index}"):
                sys_val = v
                break
        sys_name_str = _decode_bytes_str(sys_val)

        # Find management IP
        man_ip = man_ips.get((loc_port_num, rem_index))

        local_port_name = loc_ports.get(loc_port_num, f"Port {loc_port_num}")

        neighbors.append(
            {
                "local_port_num": loc_port_num,
                "local_port_name": local_port_name,
                "remote_chassis_id": chassis_str,
                "remote_port_id": port_id_str or "-",
                "remote_sys_name": sys_name_str or "-",
                "remote_man_ip": man_ip,
            }
        )

    return neighbors


def match_remote_device(
    remote_man_ip: Optional[str],
    remote_chassis_id: Optional[str],
    remote_sys_name: Optional[str],
    devices: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Match remote neighbor information to a managed Device in the database."""
    # 1. Match by Management IP
    if remote_man_ip:
        for d in devices:
            if d.get("ip_address") and d["ip_address"] == remote_man_ip:
                return d

    # 2. Match by Chassis MAC
    norm_chassis = normalize_mac(remote_chassis_id)
    if norm_chassis:
        for d in devices:
            if d.get("mac_address") and normalize_mac(d["mac_address"]) == norm_chassis:
                return d

    # 3. Match by SysName
    if remote_sys_name and remote_sys_name not in ("-", "unknown", ""):
        sys_clean = remote_sys_name.strip().lower()
        for d in devices:
            d_name = (d.get("name") or "").strip().lower()
            if d_name and (d_name == sys_clean or d_name in sys_clean or sys_clean in d_name):
                return d

    return None


def merge_lldp_links(raw_observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge directional LLDP link observations into paired topology links with confirmation status."""
    paired_links: Dict[str, Dict[str, Any]] = {}

    for obs in raw_observations:
        s_id = obs["local_device_id"]
        t_id = obs["remote_device_id"]
        s_port = obs.get("local_port")
        t_port = obs.get("remote_port")

        if s_id == t_id or not t_id:
            continue

        pair_key = f"{min(s_id, t_id)}_{max(s_id, t_id)}"

        if pair_key not in paired_links:
            paired_links[pair_key] = {
                "source_id": s_id,
                "source_name": obs.get("local_device_name"),
                "source_port": s_port,
                "target_id": t_id,
                "target_name": obs.get("remote_device_name"),
                "target_port": t_port,
                "is_bidirectional": False,
                "remote_chassis_id": obs.get("remote_chassis_id"),
                "remote_sys_name": obs.get("remote_sys_name"),
            }
        else:
            # Other side confirmed!
            existing = paired_links[pair_key]
            existing["is_bidirectional"] = True
            # Fill missing ports if any
            if not existing.get("target_port") and t_port:
                existing["target_port"] = t_port
            if not existing.get("source_port") and s_port:
                existing["source_port"] = s_port

    return list(paired_links.values())


def extract_port_number(port_str: Optional[str]) -> Optional[int]:
    """Extract a 1-48 integer port number from port strings like 'GigabitEthernet0/0/24' or '24'."""
    if not port_str:
        return None
    # If already pure integer
    if port_str.isdigit():
        val = int(port_str)
        if 1 <= val <= 48:
            return val

    # Try pattern like 0/0/24 or 1/0/5 or port 24
    matches = re.findall(r"\d+", port_str)
    if matches:
        last_num = int(matches[-1])
        if 1 <= last_num <= 48:
            return last_num
    return None


def get_device_lldp_neighbors(
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
) -> List[Dict[str, Any]]:
    """Walk LLDP MIB on a single device and return parsed neighbor list."""
    # 1. Walk local port mapping
    loc_ports_raw = snmp_walk(
        ip, community, OID_LLDP_LOC_PORT_DESC, port, version, timeout, max_entries=100
    )
    if not loc_ports_raw:
        loc_ports_raw = snmp_walk(
            ip, community, OID_LLDP_LOC_PORT_ID, port, version, timeout, max_entries=100
        )
    # Fallback to standard IF-MIB if loc ports not found
    if not loc_ports_raw:
        loc_ports_raw = snmp_walk(
            ip, community, OID_IF_DESCR, port, version, timeout, max_entries=100
        )
        if not loc_ports_raw:
            loc_ports_raw = snmp_walk(
                ip, community, OID_IF_NAME, port, version, timeout, max_entries=100
            )

    loc_ports: Dict[int, str] = {}
    for oid, val in loc_ports_raw.items():
        try:
            idx = int(oid.strip(".").split(".")[-1])
            loc_ports[idx] = _decode_bytes_str(val)
        except Exception:
            pass

    # 2. Walk remote tables
    rem_chassis = snmp_walk(
        ip, community, OID_LLDP_REM_CHASSIS_ID, port, version, timeout, max_entries=500
    )
    rem_ports = snmp_walk(
        ip, community, OID_LLDP_REM_PORT_ID, port, version, timeout, max_entries=500
    )
    rem_sysnames = snmp_walk(
        ip, community, OID_LLDP_REM_SYS_NAME, port, version, timeout, max_entries=500
    )
    rem_man_addrs = snmp_walk(
        ip, community, OID_LLDP_REM_MAN_ADDR, port, version, timeout, max_entries=500
    )

    return parse_lldp_rem_table(
        rem_chassis=rem_chassis,
        rem_ports=rem_ports,
        rem_sysnames=rem_sysnames,
        rem_man_addrs=rem_man_addrs,
        loc_ports=loc_ports,
    )


def discover_all_lldp_topology(db: Session) -> Dict[str, Any]:
    """Scan all manageable switches in DB, discover LLDP neighbor links, and match with devices."""
    switches = (
        db.scalars(
            select(Device).where(
                Device.snmp_enabled == True,
                Device.ip_address.isnot(None),
                Device.type.in_(["switch", "router", "gateway"]),
            )
        ).all()
    )

    all_devices = db.scalars(select(Device)).all()
    device_dicts = [
        {
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "ip_address": d.ip_address,
            "mac_address": d.mac_address,
            "port_count": d.port_count,
            "port_bindings": d.port_bindings or {},
        }
        for d in all_devices
    ]

    raw_observations = []
    unmatched_neighbors = []

    for sw in switches:
        try:
            comm = sw.snmp_community or "public"
            port = sw.snmp_port or 161
            ver = sw.snmp_version or "v2c"
            neighbors = get_device_lldp_neighbors(sw.ip_address, comm, port, ver)

            for n in neighbors:
                matched = match_remote_device(
                    remote_man_ip=n.get("remote_man_ip"),
                    remote_chassis_id=n.get("remote_chassis_id"),
                    remote_sys_name=n.get("remote_sys_name"),
                    devices=device_dicts,
                )

                if matched:
                    raw_observations.append(
                        {
                            "local_device_id": sw.id,
                            "local_device_name": sw.name,
                            "local_port": n["local_port_name"],
                            "remote_device_id": matched["id"],
                            "remote_device_name": matched["name"],
                            "remote_port": n["remote_port_id"],
                            "remote_chassis_id": n.get("remote_chassis_id"),
                            "remote_sys_name": n.get("remote_sys_name"),
                        }
                    )
                else:
                    unmatched_neighbors.append(
                        {
                            "collector_device_id": sw.id,
                            "collector_device_name": sw.name,
                            "local_port": n["local_port_name"],
                            "remote_chassis_id": n.get("remote_chassis_id"),
                            "remote_port": n["remote_port_id"],
                            "remote_sys_name": n.get("remote_sys_name"),
                            "remote_man_ip": n.get("remote_man_ip"),
                        }
                    )
        except Exception:
            pass

    links = merge_lldp_links(raw_observations)
    return {
        "links": links,
        "unmatched_neighbors": unmatched_neighbors,
        "scanned_devices_count": len(switches),
    }


def apply_lldp_topology(
    db: Session, links_to_apply: List[Dict[str, Any]], update_hierarchy: bool = True
) -> Dict[str, Any]:
    """Solidify discovered LLDP links into Device port_bindings and optionally update parent_id."""
    applied_count = 0

    for link in links_to_apply:
        s_id = link.get("source_id")
        t_id = link.get("target_id")
        s_port_raw = link.get("source_port")
        t_port_raw = link.get("target_port")

        if not s_id or not t_id:
            continue

        dev_source = db.get(Device, s_id)
        dev_target = db.get(Device, t_id)
        if not dev_source or not dev_target:
            continue

        # Extract port numbers (1-48) if available
        s_port_num = extract_port_number(s_port_raw)
        t_port_num = extract_port_number(t_port_raw)

        # Update Source port_bindings if source has port_count and port_num
        if s_port_num and dev_source.port_count and 1 <= s_port_num <= dev_source.port_count:
            curr_b = dict(dev_source.port_bindings or {})
            curr_b[str(s_port_num)] = {
                "target_id": t_id,
                "type": "downlink",
                "description": f"LLDP link to {dev_target.name} ({t_port_raw})",
            }
            dev_source.port_bindings = curr_b
            applied_count += 1

        # Update Target port_bindings if target has port_count and port_num
        if t_port_num and dev_target.port_count and 1 <= t_port_num <= dev_target.port_count:
            curr_b = dict(dev_target.port_bindings or {})
            curr_b[str(t_port_num)] = {
                "target_id": s_id,
                "type": "uplink",
                "description": f"LLDP link to {dev_source.name} ({s_port_raw})",
            }
            dev_target.port_bindings = curr_b
            applied_count += 1

        # Hierarchy update: if update_hierarchy is enabled, make target the child of source (or vice versa if target is core)
        if update_hierarchy:
            if dev_source.parent_id is None and dev_target.parent_id is None:
                # If target is core/root, source becomes child of target; else target child of source
                if "核心" in dev_target.name or "core" in dev_target.name.lower():
                    dev_source.parent_id = dev_target.id
                else:
                    dev_target.parent_id = dev_source.id

    db.commit()
    return {"status": "ok", "applied_count": applied_count}
