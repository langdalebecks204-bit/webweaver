import os
import re
import subprocess
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device
from app.services.oui import lookup_vendor, normalize_mac
from app.services.snmp import (
    OID_IF_DESCR,
    OID_IF_NAME,
    OID_IP_NET_TO_MEDIA_PHYS,
    snmp_walk,
)


def _format_mac_from_val(val: Any) -> Optional[str]:
    if isinstance(val, (bytes, bytearray)):
        if len(val) == 6:
            return ":".join(f"{b:02X}" for b in val)
        elif len(val) == 0:
            return None
        # In case it's a string inside bytes
        try:
            val_str = val.decode("utf-8", errors="ignore")
            norm = normalize_mac(val_str)
            if norm:
                return norm
        except Exception:
            pass
    elif isinstance(val, str):
        return normalize_mac(val)
    return None


def parse_snmp_arp_entries(
    phys_dict: Dict[str, Any], if_names: Optional[Dict[int, str]] = None
) -> List[Dict[str, Any]]:
    """Parse raw SNMP walk dictionary for ipNetToMediaPhysAddress into structured entries."""
    entries = []
    if_names = if_names or {}

    for oid, val in phys_dict.items():
        mac = _format_mac_from_val(val)
        if not mac:
            continue
        # Filter out broadcast and empty MACs
        if mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
            continue

        parts = oid.strip(".").split(".")
        # Expected OID ending: ... .ifIndex.ip1.ip2.ip3.ip4 (at least 5 parts)
        if len(parts) < 5:
            continue

        try:
            ip_parts = parts[-4:]
            ip = ".".join(ip_parts)
            if_index = int(parts[-5])
        except Exception:
            continue

        # Check if ip looks like a valid IPv4
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
            continue

        # Ignore multicast (224.0.0.0 - 239.255.255.255) and subnet broadcast
        first_octet = int(ip_parts[0])
        if first_octet >= 224:
            continue

        if_name = if_names.get(if_index, f"Port {if_index}")
        vendor = lookup_vendor(mac)

        entries.append(
            {
                "ip": ip,
                "mac": mac,
                "if_index": if_index,
                "if_name": if_name,
                "vendor": vendor,
                "source": "snmp",
            }
        )

    return entries


def parse_windows_arp_output(output: str) -> List[Dict[str, Any]]:
    """Parse Windows 'arp -a' command text output."""
    entries = []
    # Pattern matching: 192.168.1.1   70-79-90-12-34-56   动态
    pattern = re.compile(
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+(\S+)"
    )

    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        ip, raw_mac, _type = match.groups()
        mac = normalize_mac(raw_mac)
        if not mac or mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
            continue

        first_octet = int(ip.split(".")[0])
        if first_octet >= 224 or ip.endswith(".255"):
            continue

        vendor = lookup_vendor(mac)
        entries.append(
            {
                "ip": ip,
                "mac": mac,
                "if_index": None,
                "if_name": "Local ARP",
                "vendor": vendor,
                "source": "local",
            }
        )

    return entries


def parse_linux_arp_output(output: str) -> List[Dict[str, Any]]:
    """Parse Linux /proc/net/arp file content."""
    entries = []
    # Format: IP address HW type Flags HW address Mask Device
    pattern = re.compile(
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+\S+\s+\S+\s+([0-9a-fA-F:]{17})\s+\S+\s+(\S+)"
    )

    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        ip, raw_mac, dev = match.groups()
        mac = normalize_mac(raw_mac)
        if not mac or mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
            continue

        first_octet = int(ip.split(".")[0])
        if first_octet >= 224 or ip.endswith(".255"):
            continue

        vendor = lookup_vendor(mac)
        entries.append(
            {
                "ip": ip,
                "mac": mac,
                "if_index": None,
                "if_name": dev,
                "vendor": vendor,
                "source": "local",
            }
        )

    return entries


def get_local_arp() -> List[Dict[str, Any]]:
    """Get ARP table from the current host system."""
    # 1. Try Linux /proc/net/arp
    if os.path.exists("/proc/net/arp"):
        try:
            with open("/proc/net/arp", "r", encoding="utf-8", errors="ignore") as f:
                return parse_linux_arp_output(f.read())
        except Exception:
            pass

    # 2. Try Windows / generic 'arp -a'
    try:
        res = subprocess.run(
            ["arp", "-a"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout:
            return parse_windows_arp_output(res.stdout)
    except Exception:
        pass

    return []


def get_device_arp_table(
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
) -> List[Dict[str, Any]]:
    """Query a network device (switch/router) via SNMP to get its ARP table."""
    # 1. Walk descriptions and names to resolve ifIndex to ifName
    descrs = snmp_walk(ip, community, OID_IF_DESCR, port, version, timeout, max_entries=500)
    names = snmp_walk(ip, community, OID_IF_NAME, port, version, timeout, max_entries=500)

    if_names = {}
    for oid, val in descrs.items():
        try:
            idx = int(oid.strip(".").split(".")[-1])
            if isinstance(val, (bytes, bytearray)):
                val = val.decode("utf-8", errors="ignore")
            if_names[idx] = str(val)
        except Exception:
            pass

    for oid, val in names.items():
        try:
            idx = int(oid.strip(".").split(".")[-1])
            if isinstance(val, (bytes, bytearray)):
                val = val.decode("utf-8", errors="ignore")
            if idx not in if_names or not if_names[idx]:
                if_names[idx] = str(val)
        except Exception:
            pass

    # 2. Walk ARP table
    phys_dict = snmp_walk(
        ip, community, OID_IP_NET_TO_MEDIA_PHYS, port, version, timeout, max_entries=2000
    )
    return parse_snmp_arp_entries(phys_dict, if_names)


def get_consolidated_assets(
    db: Session, target_device_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetch ARP table(s), merge with known Devices in DB, and return unified asset list."""
    arp_records: List[Dict[str, Any]] = []

    if target_device_id is not None:
        device = db.get(Device, target_device_id)
        if device and device.ip_address:
            comm = device.snmp_community or "public"
            port = device.snmp_port or 161
            ver = device.snmp_version or "v2c"
            dev_entries = get_device_arp_table(device.ip_address, comm, port, ver)
            for e in dev_entries:
                e["collector_device_id"] = device.id
                e["collector_device_name"] = device.name
            arp_records.extend(dev_entries)
    else:
        # Scan all manageable switches / routers
        candidate_devices = (
            db.scalars(
                select(Device).where(
                    Device.snmp_enabled == True,
                    Device.ip_address.isnot(None),
                    Device.type.in_(["switch", "router", "gateway"]),
                )
            ).all()
        )
        for d in candidate_devices:
            try:
                comm = d.snmp_community or "public"
                port = d.snmp_port or 161
                ver = d.snmp_version or "v2c"
                dev_entries = get_device_arp_table(d.ip_address, comm, port, ver, timeout=0.8)
                for e in dev_entries:
                    e["collector_device_id"] = d.id
                    e["collector_device_name"] = d.name
                arp_records.extend(dev_entries)
            except Exception:
                pass

        # Also merge local host ARP
        local_entries = get_local_arp()
        for e in local_entries:
            e["collector_device_id"] = None
            e["collector_device_name"] = "WebWeaver Host"
        arp_records.extend(local_entries)

    # Load all registered devices to match
    all_devices = db.scalars(select(Device)).all()
    devices_by_ip = {d.ip_address: d for d in all_devices if d.ip_address}
    devices_by_mac = {d.mac_address: d for d in all_devices if d.mac_address}

    # Deduplicate by IP and MAC
    merged: Dict[str, Dict[str, Any]] = {}
    for entry in arp_records:
        ip = entry["ip"]
        mac = entry["mac"]
        key = f"{ip}_{mac}"

        if key not in merged:
            matched_dev = devices_by_ip.get(ip) or devices_by_mac.get(mac)
            is_managed = matched_dev is not None

            merged[key] = {
                "ip": ip,
                "mac": mac,
                "vendor": entry["vendor"],
                "if_index": entry.get("if_index"),
                "if_name": entry.get("if_name"),
                "collector_device_id": entry.get("collector_device_id"),
                "collector_device_name": entry.get("collector_device_name"),
                "source": entry.get("source"),
                "is_managed": is_managed,
                "managed_device_id": matched_dev.id if matched_dev else None,
                "managed_device_name": matched_dev.name if matched_dev else None,
                "managed_device_type": matched_dev.type if matched_dev else None,
                "location": matched_dev.location if matched_dev else None,
            }

    # Sort: unmanaged first, then by IP
    result = list(merged.values())

    def sort_key(item):
        ip_parts = [int(p) if p.isdigit() else 0 for p in item["ip"].split(".")]
        return (1 if item["is_managed"] else 0, ip_parts)

    result.sort(key=sort_key)
    return result
