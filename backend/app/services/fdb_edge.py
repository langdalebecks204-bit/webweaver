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


def format_terminal_default_name(
    mac: str, ip: Optional[str] = None, vendor: Optional[str] = None
) -> str:
    """Format terminal display/device name according to user specification:
    - If IP is present: "终端 ({ip})"
    - If IP is absent:
      - If vendor is known: "终端 ({vendor}{mac})" (e.g. "终端 (未知厂商C8:A3:62:DF:93:0B)")
      - Otherwise: "终端 ({mac})"
    """
    if ip:
        return f"终端 ({ip})"

    clean_mac = (mac or "").strip()
    clean_vendor = (vendor or "未知厂商").strip()
    if clean_vendor in ("", "-"):
        clean_vendor = "未知厂商"

    if clean_vendor.isascii():
        return f"终端 ({clean_vendor} {clean_mac})"
    return f"终端 ({clean_vendor}{clean_mac})"


def get_network_ip_mac_table(db: Session, all_devices: List[Device]) -> Dict[str, str]:
    """Build a mapping of normalized MAC -> IP address from all available sources:
    1. Registered devices with both IP and MAC.
    2. Manageable switches / routers ARP table via SNMP.
    3. WebWeaver host local ARP table (/proc/net/arp or arp -a).
    """
    mac_to_ip: Dict[str, str] = {}
    
    # 1. Registered devices
    for d in all_devices:
        if d.mac_address and d.ip_address:
            norm = normalize_mac(d.mac_address)
            if norm:
                mac_to_ip[norm] = d.ip_address

    # 2. Query ARP from manageable switches / routers
    try:
        from app.services.arp import get_device_arp_table, get_local_arp
        for d in all_devices:
            if d.snmp_enabled and d.ip_address and d.type in ("switch", "router", "gateway"):
                try:
                    comm = d.snmp_community or "public"
                    port = d.snmp_port or 161
                    ver = d.snmp_version or "v2c"
                    arp_entries = get_device_arp_table(d.ip_address, comm, port, ver, timeout=0.8)
                    for entry in arp_entries:
                        norm = normalize_mac(entry.get("mac"))
                        ip = entry.get("ip")
                        if norm and ip:
                            mac_to_ip.setdefault(norm, ip)
                except Exception:
                    pass

        # 3. Query local host ARP
        for entry in get_local_arp():
            norm = normalize_mac(entry.get("mac"))
            ip = entry.get("ip")
            if norm and ip:
                mac_to_ip.setdefault(norm, ip)
    except Exception:
        pass

    return mac_to_ip


def discover_edge_topology(
    db: Session, switch_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Analyze switch FDB tables to classify edge access ports:
    
    1. Single MAC ports -> Direct terminal links.
    2. Multi MAC ports with wired devices -> Unmanaged Hubs (dumb switches).
    3. Multi MAC ports with APs / randomized MACs -> AP clusters (wireless roamers).
    """
    all_devices = list(db.scalars(select(Device)))
    
    # Map normalized MAC -> Device and IP -> Device
    mac_to_dev: Dict[str, Device] = {}
    ip_to_dev: Dict[str, Device] = {}
    core_macs: set[str] = set()
    for d in all_devices:
        if d.ip_address:
            ip_to_dev[d.ip_address] = d
        if d.mac_address:
            norm = normalize_mac(d.mac_address)
            if norm:
                mac_to_dev[norm] = d
                if d.type in ("switch", "router"):
                    core_macs.add(norm)

    # Build network-wide IP-MAC map
    mac_to_ip = get_network_ip_mac_table(db, all_devices)

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

        # Find existing unmanaged switches (dumb switches) already connected to ports of this switch
        existing_port_hubs: Dict[int, Device] = {}
        if sw.port_bindings and isinstance(sw.port_bindings, dict):
            for p_str, b in sw.port_bindings.items():
                if isinstance(b, dict):
                    t_id = b.get("target_id")
                    if t_id:
                        target = db.get(Device, t_id)
                        if target and target.type == "unmanaged_switch":
                            try:
                                existing_port_hubs[int(p_str)] = target
                            except ValueError:
                                pass

        # Also check if an unmanaged switch under this switch defines an uplink port pointing to sw
        for unm in all_devices:
            if unm.parent_id == sw.id and unm.type == "unmanaged_switch":
                if unm.port_bindings and isinstance(unm.port_bindings, dict):
                    for _, ub in unm.port_bindings.items():
                        if isinstance(ub, dict) and ub.get("target_id") == sw.id:
                            tp = ub.get("target_port")
                            if tp:
                                try:
                                    existing_port_hubs.setdefault(int(tp), unm)
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
            existing_hub = existing_port_hubs.get(p_num)

            # If this port has NO existing unmanaged switch AND has exactly 1 MAC, it is a direct terminal
            if existing_hub is None and len(unique_entries) == 1:
                # Case 1: True Single MAC Direct Connection
                mac = unique_entries[0]["mac"]
                vendor = lookup_vendor(mac)
                matched_dev = mac_to_dev.get(mac)
                matched_ip = mac_to_ip.get(mac)

                # Try matching by IP if MAC was not registered on any device
                if not matched_dev and matched_ip:
                    matched_dev = ip_to_dev.get(matched_ip)

                if matched_dev:
                    dev_id = matched_dev.id
                    dev_name = matched_dev.name
                    dev_ip = matched_dev.ip_address or matched_ip
                    matched_by = "mac" if mac in mac_to_dev else "ip_mac"
                else:
                    dev_id = None
                    dev_ip = matched_ip
                    dev_name = format_terminal_default_name(mac, dev_ip, vendor)
                    matched_by = "ip_mac_unregistered" if dev_ip else "fdb_unregistered"

                direct_terminals.append({
                    "switch_id": sw.id,
                    "switch_name": sw.name,
                    "port_num": p_num,
                    "port_name": p_name,
                    "mac": mac,
                    "ip_address": dev_ip,
                    "device_id": dev_id,
                    "device_name": dev_name,
                    "matched_by": matched_by,
                    "vendor": vendor,
                })
            else:
                # Case 2: Multi MAC Port OR Port with Existing Unmanaged Switch
                random_count = 0
                mobile_count = 0
                ap_device: Optional[Device] = None

                attached_devices: List[Dict[str, Any]] = []
                unregistered_assets: List[Dict[str, Any]] = []
                seen_attached_ids: set[int] = set()

                for ue in unique_entries:
                    m = ue["mac"]
                    v = lookup_vendor(m)
                    dev = mac_to_dev.get(m)
                    matched_ip = mac_to_ip.get(m)
                    if not dev and matched_ip:
                        dev = ip_to_dev.get(matched_ip)

                    if dev and dev.type == "ap":
                        ap_device = dev

                    is_rand = is_random_mac(m)
                    is_mob = is_mobile_oui(v)
                    if is_rand:
                        random_count += 1
                    if is_mob:
                        mobile_count += 1

                    # Skip the hub itself or upstream switches/routers
                    if existing_hub and dev and dev.id == existing_hub.id:
                        continue
                    if dev and dev.type in ("switch", "router"):
                        continue

                    if dev:
                        if dev.id not in seen_attached_ids:
                            seen_attached_ids.add(dev.id)
                            attached_devices.append({
                                "device_id": dev.id,
                                "name": dev.name,
                                "mac": m,
                                "ip": dev.ip_address or matched_ip,
                                "type": dev.type,
                                "vendor": v,
                                "already_under_hub": bool(
                                    existing_hub and dev.parent_id == existing_hub.id
                                ),
                            })
                    else:
                        unregistered_assets.append({
                            "mac": m,
                            "ip": matched_ip,
                            "vendor": v,
                            "is_random_mac": is_rand,
                            "suggested_name": format_terminal_default_name(m, matched_ip, v),
                        })

                # If this port already has an unmanaged switch, include any devices already attached under it
                if existing_hub:
                    for d in all_devices:
                        if (
                            d.parent_id == existing_hub.id
                            and d.id not in seen_attached_ids
                            and d.id != existing_hub.id
                            and d.type not in ("switch", "router", "unmanaged_switch")
                        ):
                            seen_attached_ids.add(d.id)
                            attached_devices.append({
                                "device_id": d.id,
                                "name": d.name,
                                "mac": d.mac_address,
                                "ip": d.ip_address,
                                "type": d.type,
                                "vendor": lookup_vendor(d.mac_address) if d.mac_address else None,
                                "already_under_hub": True,
                            })

                total_macs = len(unique_entries)
                is_ap_scenario = existing_hub is None and (
                    ap_device is not None
                    or (total_macs > 0 and (random_count + mobile_count) / total_macs >= 0.5)
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
                    # Case 2b: Unmanaged Hub (either existing or new)
                    if existing_hub:
                        is_existing = True
                        hub_id = existing_hub.id
                        suggested_name = existing_hub.name
                    else:
                        is_existing = False
                        hub_id = None
                        suggested_name = f"{sw.name}_P{p_num}_分线交换机"

                    unmanaged_hubs.append({
                        "switch_id": sw.id,
                        "switch_name": sw.name,
                        "port_num": p_num,
                        "port_name": p_name,
                        "is_existing": is_existing,
                        "hub_id": hub_id,
                        "suggested_name": suggested_name,
                        "terminal_count": len(attached_devices) + len(unregistered_assets),
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
    
    1. Direct Terminals:
       - Check if switch port already has an unmanaged switch: if so, reparent to the unmanaged switch
         and preserve the port binding without overwriting it!
       - Otherwise: reparent to switch, bind switch port, and backfill missing mac_address / ip_address.
    2. Hubs to Create / Update:
       - If an unmanaged switch already exists on this port (by hub_id or port_binding), reuse it without
         re-creating a duplicate device and without altering existing port bindings!
       - Reparent existing devices under the hub.
       - Create new devices for unregistered MACs under the hub.
    """
    all_devices = list(db.scalars(select(Device)))
    mac_to_ip = get_network_ip_mac_table(db, all_devices)

    applied_direct_count = 0
    created_hubs_count = 0
    reused_hubs_count = 0

    # 1. Apply Direct Terminals
    for dt in direct_terminals:
        sw_id = dt.get("switch_id")
        port_num = dt.get("port_num")
        if not sw_id or not port_num:
            continue

        sw = db.get(Device, sw_id)
        if not sw:
            continue

        # Check if this switch port is ALREADY bound to an unmanaged switch
        existing_port_hub = None
        if sw.port_bindings and isinstance(sw.port_bindings, dict):
            b = sw.port_bindings.get(str(port_num))
            if isinstance(b, dict):
                t_id = b.get("target_id")
                if t_id:
                    t = db.get(Device, t_id)
                    if t and t.type == "unmanaged_switch":
                        existing_port_hub = t

        dev_id = dt.get("device_id")
        raw_mac = dt.get("mac")
        norm_mac = normalize_mac(raw_mac)
        ip = dt.get("ip_address") or (mac_to_ip.get(norm_mac) if norm_mac else None)

        target_parent_id = existing_port_hub.id if existing_port_hub else sw.id

        if dev_id:
            dev = db.get(Device, dev_id)
            if not dev:
                continue
            dev.parent_id = target_parent_id
            # 补齐资料：如果原本没有 MAC 或 IP，自动登记
            if not dev.mac_address and norm_mac:
                dev.mac_address = norm_mac
            if not dev.ip_address and ip:
                dev.ip_address = ip
        else:
            # 新终端：自动创建并入库
            if not norm_mac:
                continue
            vendor = lookup_vendor(norm_mac)
            dev_name = dt.get("device_name")
            if (
                not dev_name
                or dev_name in ("未知设备", "终端 (未知厂商)")
                or dev_name.startswith("设备 (")
                or ("未知厂商" in dev_name and norm_mac not in dev_name)
            ):
                dev_name = format_terminal_default_name(norm_mac, ip, vendor)

            dev = Device(
                name=dev_name,
                type="server",
                ip_address=ip,
                mac_address=norm_mac,
                parent_id=target_parent_id,
                status="online" if ip else "unknown",
            )
            db.add(dev)
            db.flush()

        # Update switch port binding ONLY if port does NOT already have an unmanaged switch
        if existing_port_hub is None and sw.port_count and 1 <= port_num <= sw.port_count:
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
        hub_id = hub_item.get("hub_id")

        # Determine if an unmanaged switch already exists on this port
        existing_hub = None
        if hub_id:
            existing_hub = db.get(Device, hub_id)
        if not existing_hub and sw.port_bindings and isinstance(sw.port_bindings, dict):
            b = sw.port_bindings.get(str(port_num))
            if isinstance(b, dict):
                t_id = b.get("target_id")
                if t_id:
                    t = db.get(Device, t_id)
                    if t and t.type == "unmanaged_switch":
                        existing_hub = t

        if existing_hub:
            hub = existing_hub
            # Update custom name if changed by user
            if hub_name and hub.name != hub_name:
                hub.name = hub_name
            # Ensure parent_id is sw.id
            hub.parent_id = sw.id
            # Ensure sw port binding points to hub
            if sw.port_count and 1 <= port_num <= sw.port_count:
                bindings = dict(sw.port_bindings or {})
                curr_b = bindings.get(str(port_num))
                if not curr_b or curr_b.get("target_id") != hub.id:
                    bindings[str(port_num)] = {
                        "target_id": hub.id,
                        "target_port": 1,
                        "cable_type": "copper",
                        "rate": "1000M",
                    }
                    sw.port_bindings = bindings
                    flag_modified(sw, "port_bindings")
            reused_hubs_count += 1
        else:
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

            # Bind switch port to this new Hub
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
            created_hubs_count += 1

        # Reparent existing devices under this Hub
        for d_id in hub_item.get("device_ids", []):
            if d_id == hub.id or d_id == sw.id:
                continue
            attached_dev = db.get(Device, d_id)
            if attached_dev and attached_dev.type not in ("switch", "unmanaged_switch", "router"):
                attached_dev.parent_id = hub.id

        # Enroll unregistered MACs under this Hub
        for raw_item in hub_item.get("unregistered_macs", []):
            if isinstance(raw_item, dict):
                raw_mac = raw_item.get("mac")
                item_ip = raw_item.get("ip")
                item_name = raw_item.get("name")
            else:
                raw_mac = raw_item
                item_ip = None
                item_name = None

            norm_mac = normalize_mac(raw_mac)
            if not norm_mac:
                continue
            ip = item_ip or mac_to_ip.get(norm_mac)
            vendor = lookup_vendor(norm_mac)
            if (
                item_name
                and item_name != "终端 (未知厂商)"
                and not ("未知厂商" in item_name and norm_mac not in item_name)
            ):
                name = item_name
            else:
                name = format_terminal_default_name(norm_mac, ip, vendor)

            new_dev = Device(
                name=name,
                type="server",
                ip_address=ip,
                mac_address=norm_mac,
                parent_id=hub.id,
                status="online" if ip else "unknown",
            )
            db.add(new_dev)

    db.commit()

    return {
        "applied_direct_count": applied_direct_count,
        "created_hubs_count": created_hubs_count,
        "reused_hubs_count": reused_hubs_count,
    }


