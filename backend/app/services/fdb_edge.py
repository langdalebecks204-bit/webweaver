import collections
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Device
from app.services.oui import lookup_vendor, normalize_mac
from app.services import lldp

MOBILE_VENDORS = (
    "apple",
    "xiaomi",
    "huawei device",
    "vivo",
    "oppo",
    "honor",
    "samsung electronics (mobile)",
    "samsung mobile",
    "meizu",
    "oneplus",
    "realme",
)


def is_random_mac(mac: Optional[str]) -> bool:
    """Check if MAC address has IEEE 802 Locally Administered Address (LAA) bit set.
    
    The 2nd hex digit of an LAA MAC is 2, 6, A, or E (e.g. x2:xx:xx, x6:xx:xx, xA:xx:xx, xE:xx:xx).
    In modern LANs, >99.9% of these are iOS/Android/Windows private randomized Wi-Fi MACs.
    """
    if not mac:
        return False
    clean = re.sub(r"[^0-9A-Fa-f]", "", str(mac)).upper()
    if len(clean) >= 2 and clean[1] in ("2", "6", "A", "E"):
        return True
    return False


def is_mobile_oui(vendor: Optional[str]) -> bool:
    """Check if the resolved OUI vendor name corresponds to mobile/handheld device lines."""
    if not vendor:
        return False
    v_lower = vendor.lower()
    return any(mv in v_lower for mv in MOBILE_VENDORS)


def discover_edge_topology(
    db: Session, switch_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Analyze switch FDB tables to classify edge access ports:
    
    1. Single MAC ports -> Direct terminal links.
    2. Multi MAC ports with wired devices -> Unmanaged Hubs (dumb switches).
    3. Multi MAC ports with APs / randomized MACs -> AP clusters (wireless roamers).
    """
    all_devices = list(db.scalars(select(Device)))
    
    # Map normalized MAC -> Device
    mac_to_dev: Dict[str, Device] = {}
    core_macs: set[str] = set()
    for d in all_devices:
        if d.mac_address:
            norm = normalize_mac(d.mac_address)
            if norm:
                mac_to_dev[norm] = d
                if d.type in ("switch", "router"):
                    core_macs.add(norm)

    # Filter target switches
    switches = [d for d in all_devices if d.type == "switch" and d.snmp_enabled and d.ip_address]
    if switch_ids:
        switches = [s for s in switches if s.id in switch_ids]

    direct_terminals: List[Dict[str, Any]] = []
    unmanaged_hubs: List[Dict[str, Any]] = []
    ap_clusters: List[Dict[str, Any]] = []

    for sw in switches:
        # Determine skip ports (uplink or existing inter-switch links)
        skip_ports: set[int] = set()
        if sw.uplink_port:
            skip_ports.add(sw.uplink_port)
        if sw.port_bindings and isinstance(sw.port_bindings, dict):
            for p_str, b in sw.port_bindings.items():
                if isinstance(b, dict):
                    t_id = b.get("target_id")
                    if t_id:
                        target = db.get(Device, t_id)
                        if target and target.type in ("switch", "router"):
                            try:
                                skip_ports.add(int(p_str))
                            except ValueError:
                                pass

        fdb_entries = lldp.get_device_fdb_table(
            sw.ip_address,
            sw.snmp_community or "public",
            sw.snmp_port or 161,
        )

        port_map: Dict[int, List[Dict[str, Any]]] = collections.defaultdict(list)
        port_names: Dict[int, str] = {}

        for entry in fdb_entries:
            p_num = entry.get("local_port_num")
            raw_mac = entry.get("learned_mac")
            if not p_num or p_num <= 0 or p_num in skip_ports or not raw_mac:
                continue

            norm_mac = normalize_mac(raw_mac)
            if not norm_mac:
                continue

            # Skip if this port learned a core switch/router's MAC (it's a trunk/uplink port)
            if norm_mac in core_macs:
                skip_ports.add(p_num)
                continue

            p_name = entry.get("local_port_name") or f"Port{p_num}"
            port_names[p_num] = p_name
            port_map[p_num].append({
                "mac": norm_mac,
                "port_num": p_num,
                "port_name": p_name,
            })

        # Process each non-skipped port
        for p_num, entries in port_map.items():
            if p_num in skip_ports:
                continue

            # Unique MACs on this port
            seen_macs = set()
            unique_entries = []
            for e in entries:
                if e["mac"] not in seen_macs:
                    seen_macs.add(e["mac"])
                    unique_entries.append(e)

            if not unique_entries:
                continue

            p_name = port_names.get(p_num, f"Port{p_num}")

            if len(unique_entries) == 1:
                # Case 1: Single MAC Direct Connection
                mac = unique_entries[0]["mac"]
                matched_dev = mac_to_dev.get(mac)
                vendor = lookup_vendor(mac)
                
                direct_terminals.append({
                    "switch_id": sw.id,
                    "switch_name": sw.name,
                    "port_num": p_num,
                    "port_name": p_name,
                    "mac": mac,
                    "ip_address": matched_dev.ip_address if matched_dev else None,
                    "device_id": matched_dev.id if matched_dev else None,
                    "device_name": matched_dev.name if matched_dev else (f"设备 ({vendor})" if vendor != "-" else "未知设备"),
                    "matched_by": "mac" if matched_dev else "fdb_unregistered",
                    "vendor": vendor,
                })
            else:
                # Case 2: Multi MAC Port (Unmanaged Hub or Wireless AP Cluster)
                random_count = 0
                mobile_count = 0
                ap_device: Optional[Device] = None

                attached_devices: List[Dict[str, Any]] = []
                unregistered_assets: List[Dict[str, Any]] = []

                for ue in unique_entries:
                    m = ue["mac"]
                    v = lookup_vendor(m)
                    dev = mac_to_dev.get(m)
                    
                    if dev and dev.type == "ap":
                        ap_device = dev

                    is_rand = is_random_mac(m)
                    is_mob = is_mobile_oui(v)
                    if is_rand:
                        random_count += 1
                    if is_mob:
                        mobile_count += 1

                    if dev:
                        attached_devices.append({
                            "device_id": dev.id,
                            "name": dev.name,
                            "mac": m,
                            "ip": dev.ip_address,
                            "type": dev.type,
                            "vendor": v,
                        })
                    else:
                        unregistered_assets.append({
                            "mac": m,
                            "ip": None,
                            "vendor": v,
                            "is_random_mac": is_rand,
                        })

                total_macs = len(unique_entries)
                is_ap_scenario = (
                    ap_device is not None
                    or ((random_count + mobile_count) / total_macs >= 0.5)
                )

                if is_ap_scenario:
                    # Case 2a: AP Cluster
                    ap_clusters.append({
                        "switch_id": sw.id,
                        "switch_name": sw.name,
                        "port_num": p_num,
                        "port_name": p_name,
                        "ap_device_id": ap_device.id if ap_device else None,
                        "ap_name": ap_device.name if ap_device else f"无线AP (P{p_num})",
                        "terminal_count": total_macs,
                        "mobile_count": random_count + mobile_count,
                        "has_random_macs": random_count > 0,
                        "sample_macs": [ue["mac"] for ue in unique_entries[:5]],
                    })
                else:
                    # Case 2b: Unmanaged Hub
                    suggested_name = f"{sw.name}_P{p_num}_分线交换机"
                    unmanaged_hubs.append({
                        "switch_id": sw.id,
                        "switch_name": sw.name,
                        "port_num": p_num,
                        "port_name": p_name,
                        "suggested_name": suggested_name,
                        "terminal_count": total_macs,
                        "attached_devices": attached_devices,
                        "unregistered_assets": unregistered_assets,
                    })

    return {
        "direct_terminals": direct_terminals,
        "unmanaged_hubs": unmanaged_hubs,
        "ap_clusters": ap_clusters,
    }


def apply_edge_topology(
    db: Session,
    direct_terminals: List[Dict[str, Any]],
    hubs_to_create: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply edge topology selections into database:
    
    1. Direct Terminals: Update terminal parent_id to switch and bind to switch port.
    2. Hubs to Create: Create unmanaged_switch device, link to switch port, and reparent attached devices.
    """
    applied_direct_count = 0
    created_hubs_count = 0

    # 1. Apply Direct Terminals
    for dt in direct_terminals:
        dev_id = dt.get("device_id")
        sw_id = dt.get("switch_id")
        port_num = dt.get("port_num")
        if not dev_id or not sw_id or not port_num:
            continue

        dev = db.get(Device, dev_id)
        sw = db.get(Device, sw_id)
        if not dev or not sw:
            continue

        # Update terminal parent_id to switch
        dev.parent_id = sw.id

        # Update switch port binding if port_count exists
        if sw.port_count and 1 <= port_num <= sw.port_count:
            bindings = dict(sw.port_bindings or {})
            bindings[str(port_num)] = {
                "target_id": dev.id,
                "target_port": None,
                "cable_type": "copper",
                "rate": "1000M",
            }
            sw.port_bindings = bindings
            flag_modified(sw, "port_bindings")

        applied_direct_count += 1

    # 2. Apply Hubs
    for hub_item in hubs_to_create:
        sw_id = hub_item.get("switch_id")
        port_num = hub_item.get("port_num")
        if not sw_id or not port_num:
            continue

        sw = db.get(Device, sw_id)
        if not sw:
            continue

        hub_name = (hub_item.get("name") or f"{sw.name}_P{port_num}_分线交换机").strip()
        
        # Create virtual Hub device
        hub = Device(
            name=hub_name,
            type="unmanaged_switch",
            is_virtual=True,
            parent_id=sw.id,
            port_count=8,  # Default 8 ports for unmanaged dumb switch
            uplink_port=1,
            status="online",
        )
        db.add(hub)
        db.flush()  # get hub.id

        # Bind switch port to this Hub
        if sw.port_count and 1 <= port_num <= sw.port_count:
            bindings = dict(sw.port_bindings or {})
            bindings[str(port_num)] = {
                "target_id": hub.id,
                "target_port": 1,
                "cable_type": "copper",
                "rate": "1000M",
            }
            sw.port_bindings = bindings
            flag_modified(sw, "port_bindings")

        # Reparent existing devices under this Hub
        for d_id in hub_item.get("device_ids", []):
            attached_dev = db.get(Device, d_id)
            if attached_dev:
                attached_dev.parent_id = hub.id

        # Enroll unregistered MACs under this Hub
        for raw_mac in hub_item.get("unregistered_macs", []):
            norm_mac = normalize_mac(raw_mac)
            if not norm_mac:
                continue
            vendor = lookup_vendor(norm_mac)
            new_dev = Device(
                name=f"终端 ({vendor})" if vendor != "-" else f"未登记终端 ({norm_mac[-5:]})",
                type="server",
                mac_address=norm_mac,
                parent_id=hub.id,
                status="unknown",
            )
            db.add(new_dev)

        created_hubs_count += 1

    db.commit()

    return {
        "applied_direct_count": applied_direct_count,
        "created_hubs_count": created_hubs_count,
    }

