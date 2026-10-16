import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device
from app.services.oui import normalize_mac, lookup_vendor
from app.services.snmp import (
    OID_IF_DESCR,
    OID_IF_NAME,
    OID_DOT1D_BASE_BRIDGE_ADDRESS,
    OID_DOT1D_BASE_PORT_IF_INDEX,
    OID_DOT1D_TP_FDB_PORT,
    OID_DOT1D_TP_FDB_STATUS,
    OID_LLDP_LOC_PORT_DESC,
    OID_LLDP_LOC_PORT_ID,
    OID_LLDP_REM_CHASSIS_ID,
    OID_LLDP_REM_MAN_ADDR,
    OID_LLDP_REM_PORT_DESC,
    OID_LLDP_REM_PORT_ID,
    OID_LLDP_REM_SYS_NAME,
    snmp_walk,
    snmp_get_scalar,
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


def get_switch_base_mac(
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
) -> Optional[str]:
    """Query dot1dBaseBridgeAddress (1.3.6.1.2.1.17.1.1.0) for switch Base MAC."""
    val = snmp_get_scalar(ip, community, OID_DOT1D_BASE_BRIDGE_ADDRESS, port, version, timeout)
    if isinstance(val, (bytes, bytearray)) and len(val) == 6:
        return ":".join(f"{b:02X}" for b in val)
    elif isinstance(val, str):
        return normalize_mac(val)
    return None


def get_device_fdb_table(
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
) -> List[Dict[str, Any]]:
    """Walk Bridge-MIB dot1dTpFdbTable (1.3.6.1.2.1.17.4.3.1.2) and return learned MAC -> Port mappings."""
    # 1. Walk local port mapping
    loc_ports_raw = snmp_walk(ip, community, OID_IF_DESCR, port, version, timeout, max_entries=100)
    if not loc_ports_raw:
        loc_ports_raw = snmp_walk(ip, community, OID_IF_NAME, port, version, timeout, max_entries=100)

    loc_ports: Dict[int, str] = {}
    for oid, val in loc_ports_raw.items():
        try:
            idx = int(oid.strip(".").split(".")[-1])
            loc_ports[idx] = _decode_bytes_str(val)
        except Exception:
            pass

    # 2. Bridge port to ifIndex mapping (1.3.6.1.2.1.17.1.4.1.2)
    bp_to_if: Dict[int, int] = {}
    bp_raw = snmp_walk(ip, community, OID_DOT1D_BASE_PORT_IF_INDEX, port, version, timeout, max_entries=100)
    for oid, val in bp_raw.items():
        try:
            b_port = int(oid.strip(".").split(".")[-1])
            if isinstance(val, int):
                bp_to_if[b_port] = val
        except Exception:
            pass

    # 3. FDB Port table (1.3.6.1.2.1.17.4.3.1.2)
    fdb_raw = snmp_walk(ip, community, OID_DOT1D_TP_FDB_PORT, port, version, timeout, max_entries=500)
    # 4. FDB Status (1.3.6.1.2.1.17.4.3.1.3): 3=learned, 4=self, 5=mgmt
    status_raw = snmp_walk(ip, community, OID_DOT1D_TP_FDB_STATUS, port, version, timeout, max_entries=500)

    entries = []
    for oid, port_val in fdb_raw.items():
        parts = oid.strip(".").split(".")
        if len(parts) < 6:
            continue
        try:
            mac_decimals = [int(p) for p in parts[-6:]]
            mac_str = ":".join(f"{b:02X}" for b in mac_decimals)
        except Exception:
            continue

        # Ignore broadcast / multicast
        if mac_str.startswith("01:00:5E") or mac_str.startswith("33:33") or mac_str == "FF:FF:FF:FF:FF:FF":
            continue

        status_oid = f"{OID_DOT1D_TP_FDB_STATUS}.{'.'.join(parts[-6:])}"
        if status_raw.get(status_oid) in (4, 5):  # self / management address
            continue

        bridge_port = int(port_val) if isinstance(port_val, int) else None
        if not bridge_port or bridge_port <= 0:
            continue

        if_idx = bp_to_if.get(bridge_port, bridge_port)
        port_name = loc_ports.get(if_idx) or loc_ports.get(bridge_port) or f"Port {bridge_port}"

        entries.append({
            "local_port_num": bridge_port,
            "local_port_name": port_name,
            "learned_mac": mac_str,
        })

    return entries


def discover_all_lldp_topology(db: Session) -> Dict[str, Any]:
    """Scan all manageable switches in DB via LLDP and Bridge-MIB FDB, discovering physical topology."""
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

    # Pre-fetch Base MAC for switches if missing
    for sw in switches:
        if not sw.mac_address and sw.ip_address:
            try:
                base_mac = get_switch_base_mac(
                    sw.ip_address,
                    sw.snmp_community or "public",
                    sw.snmp_port or 161,
                    sw.snmp_version or "v2c",
                )
                if base_mac:
                    sw.mac_address = base_mac
            except Exception:
                pass
    try:
        db.commit()
    except Exception:
        db.rollback()

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

    mac_to_device = {}
    for d in device_dicts:
        if d.get("mac_address"):
            norm = normalize_mac(d["mac_address"])
            if norm:
                mac_to_device[norm] = d

    raw_observations = []
    unmatched_neighbors = []

    for sw in switches:
        try:
            comm = sw.snmp_community or "public"
            port = sw.snmp_port or 161
            ver = sw.snmp_version or "v2c"

            # 1. Try Standard LLDP first
            neighbors = get_device_lldp_neighbors(sw.ip_address, comm, port, ver)

            # 2. If no LLDP neighbors (e.g. whitebox / TP-Link switches), fallback to Bridge FDB MAC table
            if not neighbors:
                fdb_table = get_device_fdb_table(sw.ip_address, comm, port, ver)
                # Group learned MACs by port
                port_macs: Dict[str, List[str]] = {}
                for entry in fdb_table:
                    port_macs.setdefault(entry["local_port_name"], []).append(entry["learned_mac"])

                for p_name, macs in port_macs.items():
                    matched_on_port = False
                    for m in macs:
                        norm_m = normalize_mac(m)
                        if norm_m and norm_m in mac_to_device:
                            matched_dev = mac_to_device[norm_m]
                            if matched_dev["id"] != sw.id:
                                raw_observations.append({
                                    "local_device_id": sw.id,
                                    "local_device_name": sw.name,
                                    "local_port": p_name,
                                    "remote_device_id": matched_dev["id"],
                                    "remote_device_name": matched_dev["name"],
                                    "remote_port": None,
                                    "remote_chassis_id": norm_m,
                                    "remote_sys_name": matched_dev["name"],
                                })
                                matched_on_port = True
                                break
                    if not matched_on_port:
                        # Report unmatched external device if single/few MACs on port (likely direct connection)
                        for m in macs[:3]:
                            norm_m = normalize_mac(m)
                            if norm_m:
                                vendor = lookup_vendor(norm_m)
                                unmatched_neighbors.append({
                                    "collector_device_id": sw.id,
                                    "collector_device_name": sw.name,
                                    "local_port": p_name,
                                    "remote_chassis_id": norm_m,
                                    "remote_port": "-",
                                    "remote_sys_name": vendor if vendor != "未知厂商" else "-",
                                    "remote_man_ip": None,
                                })
            else:
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


def diag_lldp_connection(
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.5,
) -> Dict[str, Any]:
    """Diagnose SNMP, LLDP, and CDP connectivity for a specific switch with raw details."""
    report: Dict[str, Any] = {
        "target_ip": ip,
        "community": community,
        "port": port,
        "version": version,
        "basic_snmp_ok": False,
        "basic_snmp_sample": {},
        "raw_lldp_response": {},
        "lldp_neighbors_count": 0,
        "lldp_neighbors": [],
        "cdp_neighbors_count": 0,
        "cdp_neighbors": [],
        "diagnosis_tips": [],
    }

    import socket
    from app.services.snmp import (
        build_snmp_getnext_packet,
        decode_asn1,
        snmp_walk,
        OID_IF_DESCR,
        OID_IF_NAME,
        OID_LLDP_REM_CHASSIS_ID,
        OID_LLDP_LOC_PORT_DESC,
    )

    # 1. Test basic SNMP (IF-MIB)
    try:
        descrs = snmp_walk(ip, community, OID_IF_DESCR, port, version, timeout=timeout, max_entries=5)
        if not descrs:
            descrs = snmp_walk(ip, community, OID_IF_NAME, port, version, timeout=timeout, max_entries=5)

        if descrs:
            report["basic_snmp_ok"] = True
            report["basic_snmp_sample"] = {k: _decode_bytes_str(v) for k, v in list(descrs.items())[:3]}
        else:
            report["diagnosis_tips"].append(
                "基础 SNMP (IF-MIB) 无响应。请检查：1. 交换机 SNMP 团体字是否正确；2. 交换机是否允许服务器 IP 访问 UDP 161 端口。"
            )
    except Exception as e:
        report["diagnosis_tips"].append(f"基础 SNMP 测试异常: {str(e)}")

    # 2. Raw GetNext against OID_LLDP_REM_CHASSIS_ID (1.0.8802.1.1.2.1.4.1.1.5)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    raw_info = {"status": "timeout_or_error", "returned_oid": None, "returned_tag": None, "raw_val": None}
    try:
        req_pkt = build_snmp_getnext_packet(community, OID_LLDP_REM_CHASSIS_ID, request_id=888, version=version)
        sock.sendto(req_pkt, (ip, port))
        data, _ = sock.recvfrom(4096)
        _, msg_el, _ = decode_asn1(data)
        if isinstance(msg_el, list) and len(msg_el) >= 3:
            pdu_el = msg_el[2]
            if isinstance(pdu_el, list) and len(pdu_el) >= 4:
                varbinds = pdu_el[3]
                if isinstance(varbinds, list) and varbinds:
                    first_vb = varbinds[0]
                    if isinstance(first_vb, list) and len(first_vb) >= 2:
                        ret_oid = first_vb[0]
                        ret_val = first_vb[1]
                        raw_info["status"] = "received"
                        raw_info["returned_oid"] = str(ret_oid)
                        raw_info["raw_val"] = repr(ret_val)

                        if ret_oid.startswith("1.0.8802."):
                            raw_info["is_lldp_tree"] = True
                        else:
                            raw_info["is_lldp_tree"] = False
                            report["diagnosis_tips"].append(
                                f"交换机对 1.0.8802 请求返回了下一个 OID: {ret_oid}（跳过了 LLDP 树）！"
                                "根本原因：交换机 SNMP MIB-View 视图限制了仅允许 1.3.6.1（internet），未包含 1.0.8802 或 iso！"
                                "请在交换机 Web 界面 SNMP 设置中，将 MIB View 切换为 'all' 或在命令行配置包含 iso / 1.0.8802。"
                            )
    except socket.timeout:
        raw_info["status"] = "timeout"
        report["diagnosis_tips"].append(
            "针对 1.0.8802 LLDP OID 发送请求超时。可能是交换机未向该 SNMP 团体字开放该 MIB 树或未开启 LLDP。"
        )
    except Exception as e:
        raw_info["error"] = str(e)
    finally:
        sock.close()
    report["raw_lldp_response"] = raw_info

    # 3. Full LLDP parsing
    try:
        neighbors = get_device_lldp_neighbors(ip, community, port, version, timeout=timeout)
        report["lldp_neighbors_count"] = len(neighbors)
        report["lldp_neighbors"] = neighbors
        if not neighbors and report["basic_snmp_ok"] and raw_info.get("is_lldp_tree"):
            report["diagnosis_tips"].append(
                "交换机支持 LLDP-MIB，但当前没有邻居条目。请确认下级连接的交换机/AP 是否也已开启 LLDP。"
            )
    except Exception as e:
        report["diagnosis_tips"].append(f"LLDP 完整解析异常: {str(e)}")

    # 4. Check Cisco CDP
    try:
        cdp_devs = snmp_walk(ip, community, "1.3.6.1.4.1.9.9.23.1.2.1.1.6", port, version, timeout=timeout, max_entries=20)
        report["cdp_neighbors_count"] = len(cdp_devs)
        report["cdp_neighbors"] = [_decode_bytes_str(v) for v in cdp_devs.values()]
        if cdp_devs:
            report["diagnosis_tips"].append(
                f"检测到交换机存在 {len(cdp_devs)} 个 Cisco CDP 邻居。如果交换机支持，建议也开启 LLDP 协议。"
            )
    except Exception:
        pass

    return report

