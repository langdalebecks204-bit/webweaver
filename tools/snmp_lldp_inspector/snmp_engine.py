import os
import re
import socket
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure local oui module can be loaded regardless of import origin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from oui import lookup_vendor, normalize_mac
except ImportError:
    from .oui import lookup_vendor, normalize_mac

# Standard MIB-II System OIDs
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

# IF-MIB
OID_IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"

# BRIDGE-MIB (RFC 1493)
OID_DOT1D_BASE_BRIDGE_ADDRESS = "1.3.6.1.2.1.17.1.1.0"
OID_DOT1D_BASE_PORT_IF_INDEX = "1.3.6.1.2.1.17.1.4.1.2"
OID_DOT1D_TP_FDB_PORT = "1.3.6.1.2.1.17.4.3.1.2"
OID_DOT1D_TP_FDB_STATUS = "1.3.6.1.2.1.17.4.3.1.3"

# LLDP-MIB (IEEE 802.1AB)
OID_LLDP_LOC_PORT_ID = "1.0.8802.1.1.2.1.3.7.1.3"
OID_LLDP_LOC_PORT_DESC = "1.0.8802.1.1.2.1.3.7.1.4"
OID_LLDP_REM_CHASSIS_ID = "1.0.8802.1.1.2.1.4.1.1.5"
OID_LLDP_REM_PORT_ID = "1.0.8802.1.1.2.1.4.1.1.7"
OID_LLDP_REM_PORT_DESC = "1.0.8802.1.1.2.1.4.1.1.8"
OID_LLDP_REM_SYS_NAME = "1.0.8802.1.1.2.1.4.1.1.9"
OID_LLDP_REM_SYS_DESC = "1.0.8802.1.1.2.1.4.1.1.10"
OID_LLDP_REM_MAN_ADDR = "1.0.8802.1.1.2.1.4.2.1"


# --- ASN.1 / SNMP Packet Encoding & Decoding ---

def encode_asn1_length(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    elif length < 256:
        return bytes([0x81, length])
    elif length < 65536:
        return bytes([0x82, length >> 8, length & 0xFF])
    raise ValueError("ASN.1 length exceeds 65535")


def encode_oid(oid_str: str) -> bytes:
    parts = [int(p) for p in oid_str.strip(".").split(".")]
    if len(parts) < 2:
        raise ValueError("Invalid OID: at least 2 components required")
    encoded = bytes([parts[0] * 40 + parts[1]])
    for sub in parts[2:]:
        if sub == 0:
            encoded += b"\x00"
        else:
            sub_bytes = []
            while sub > 0:
                sub_bytes.append((sub & 0x7F) | 0x80)
                sub >>= 7
            sub_bytes[0] &= 0x7F
            encoded += bytes(reversed(sub_bytes))
    return encoded


def decode_asn1_length(data: bytes, offset: int) -> Tuple[int, int]:
    first = data[offset]
    if first < 128:
        return first, offset + 1
    num_bytes = first & 0x7F
    length = 0
    for i in range(num_bytes):
        length = (length << 8) + data[offset + 1 + i]
    return length, offset + 1 + num_bytes


def decode_asn1(data: bytes, offset: int = 0) -> Tuple[int, Any, int]:
    tag = data[offset]
    length, next_off = decode_asn1_length(data, offset + 1)
    val_data = data[next_off : next_off + length]
    end_off = next_off + length

    if tag in (0x30, 0xA0, 0xA1, 0xA2, 0xA3):  # SEQUENCE or PDU
        sub_off = next_off
        elements = []
        while sub_off < end_off:
            _, val, sub_off = decode_asn1(data, sub_off)
            elements.append(val)
        return tag, elements, end_off
    elif tag in (0x02, 0x41, 0x42, 0x43):  # INTEGER / Counter32 / Gauge32 / TimeTicks
        val = int.from_bytes(val_data, byteorder="big", signed=False)
        return tag, val, end_off
    elif tag == 0x46:  # Counter64
        val = int.from_bytes(val_data, byteorder="big", signed=False)
        return tag, val, end_off
    elif tag == 0x04:  # OCTET STRING
        return tag, val_data, end_off
    elif tag == 0x06:  # OBJECT IDENTIFIER
        if not val_data:
            return tag, "", end_off
        oid_parts = [val_data[0] // 40, val_data[0] % 40]
        val = 0
        for b in val_data[1:]:
            val = (val << 7) | (b & 0x7F)
            if not (b & 0x80):
                oid_parts.append(val)
                val = 0
        return tag, ".".join(str(p) for p in oid_parts), end_off
    else:
        return tag, val_data, end_off


def build_snmp_packet(pdu_type: int, community: str, oid_str: str, request_id: int = 100, version: str = "v2c") -> bytes:
    ver_num = 1 if version == "v2c" else 0
    ver_bytes = b"\x02\x01" + bytes([ver_num])

    comm_bytes = community.encode("utf-8")
    comm_asn1 = b"\x04" + encode_asn1_length(len(comm_bytes)) + comm_bytes

    oid_bytes = encode_oid(oid_str)
    varbind = (
        b"\x30"
        + encode_asn1_length(len(oid_bytes) + 4)
        + b"\x06"
        + encode_asn1_length(len(oid_bytes))
        + oid_bytes
        + b"\x05\x00"  # NULL value
    )
    varbind_list = b"\x30" + encode_asn1_length(len(varbind)) + varbind

    req_id_bytes = request_id.to_bytes(4, byteorder="big")
    pdu_contents = (
        b"\x02\x04" + req_id_bytes + b"\x02\x01\x00\x02\x01\x00" + varbind_list
    )
    pdu = bytes([pdu_type]) + encode_asn1_length(len(pdu_contents)) + pdu_contents

    message = (
        b"\x30"
        + encode_asn1_length(len(ver_bytes) + len(comm_asn1) + len(pdu))
        + ver_bytes
        + comm_asn1
        + pdu
    )
    return message


# --- Low-Level SNMP Operations ---

def snmp_get_scalar(
    ip: str,
    community: str,
    oid_str: str,
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
) -> Optional[Any]:
    """Query a single SNMP scalar OID with GetRequest and fallback to GetNextRequest."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        # Try GetRequest (0xA0)
        pkt = build_snmp_packet(0xA0, community, oid_str, request_id=1, version=version)
        sock.sendto(pkt, (ip, port))
        data, _ = sock.recvfrom(4096)
        _, msg_el, _ = decode_asn1(data)
        if isinstance(msg_el, list) and len(msg_el) >= 3:
            pdu_el = msg_el[2]
            if isinstance(pdu_el, list) and len(pdu_el) >= 4 and pdu_el[1] == 0:  # error_status == 0
                vbs = pdu_el[3]
                if isinstance(vbs, list) and vbs and len(vbs[0]) >= 2:
                    return vbs[0][1]
    except Exception:
        pass
    finally:
        sock.close()

    # Fallback to GetNextRequest (0xA1)
    root_query = oid_str.rstrip(".0") if oid_str.endswith(".0") else oid_str
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        pkt = build_snmp_packet(0xA1, community, root_query, request_id=2, version=version)
        sock.sendto(pkt, (ip, port))
        data, _ = sock.recvfrom(4096)
        _, msg_el, _ = decode_asn1(data)
        if isinstance(msg_el, list) and len(msg_el) >= 3:
            pdu_el = msg_el[2]
            if isinstance(pdu_el, list) and len(pdu_el) >= 4 and pdu_el[1] == 0:
                vbs = pdu_el[3]
                if isinstance(vbs, list) and vbs and len(vbs[0]) >= 2:
                    ret_oid = str(vbs[0][0])
                    if ret_oid.startswith(root_query):
                        return vbs[0][1]
    except Exception:
        pass
    finally:
        sock.close()

    return None


def snmp_walk(
    ip: str,
    community: str,
    root_oid: str,
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.0,
    max_repetitions: int = 2000,
) -> Dict[str, Any]:
    """Walk an SNMP subtree using GetNextRequest with loop protection and monotonicity validation."""
    results: Dict[str, Any] = {}
    current_oid = root_oid.strip(".")
    root_prefix = current_oid + "."
    req_id = 100

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        for _ in range(max_repetitions):
            req_id += 1
            pkt = build_snmp_packet(0xA1, community, current_oid, request_id=req_id, version=version)
            sock.sendto(pkt, (ip, port))

            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                break

            _, msg_el, _ = decode_asn1(data)
            if not (isinstance(msg_el, list) and len(msg_el) >= 3):
                break

            pdu_el = msg_el[2]
            if not (isinstance(pdu_el, list) and len(pdu_el) >= 4):
                break

            error_status = pdu_el[1]
            if error_status != 0:
                break

            varbinds = pdu_el[3]
            if not (isinstance(varbinds, list) and varbinds):
                break

            vb = varbinds[0]
            if not (isinstance(vb, list) and len(vb) >= 2):
                break

            ret_oid = str(vb[0]).strip(".")
            ret_val = vb[1]

            # Monotonicity check to avoid infinite loop on buggy switch firmwares
            def oid_parts(o: str) -> List[int]:
                return [int(p) for p in o.split(".") if p.isdigit()]

            if oid_parts(ret_oid) <= oid_parts(current_oid):
                break

            # Check if still under root_oid
            if not (ret_oid == current_oid or ret_oid.startswith(root_prefix)):
                break

            results[ret_oid] = ret_val
            current_oid = ret_oid
    except Exception:
        pass
    finally:
        sock.close()

    return results


# --- Helpers & Data Normalization ---

def decode_bytes_str(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""
    elif isinstance(val, str):
        return val.strip()
    return str(val) if val is not None else ""


def format_mac_bytes(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        if len(val) == 6:
            return ":".join(f"{b:02X}" for b in val)
        text = decode_bytes_str(val)
        norm = normalize_mac(text)
        return norm if norm else text
    elif isinstance(val, str):
        norm = normalize_mac(val)
        return norm if norm else val.strip()
    return ""


def format_uptime(timeticks: Optional[int]) -> str:
    if timeticks is None or not isinstance(timeticks, int):
        return "未知"
    seconds = timeticks // 100
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0 or days > 0:
        parts.append(f"{hours}小时")
    parts.append(f"{mins}分{secs}秒")
    return "".join(parts)


def format_speed(bps: int) -> str:
    if bps <= 0:
        return "0 Mbps"
    if bps >= 10_000_000_000:
        return f"{bps / 1_000_000_000:.0f} Gbps"
    elif bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.1f} Gbps"
    elif bps >= 1_000_000:
        return f"{bps / 1_000_000:.0f} Mbps"
    elif bps >= 1_000:
        return f"{bps / 1_000:.0f} Kbps"
    return f"{bps} bps"


# --- High-Level Inspections ---

def inspect_system(ip: str, community: str, port: int = 161, version: str = "v2c", timeout: float = 1.0) -> Dict[str, Any]:
    """Query System MIB and Bridge Base MAC."""
    t0 = time.time()
    raw_uptime = snmp_get_scalar(ip, community, OID_SYS_UPTIME, port, version, timeout)
    latency_ms = (time.time() - t0) * 1000

    if raw_uptime is None:
        # Check if sysDescr responds
        raw_descr = snmp_get_scalar(ip, community, OID_SYS_DESCR, port, version, timeout)
        if raw_descr is None:
            return {"reachable": False, "latency_ms": latency_ms, "error": "SNMP 无应答 (可能超时、团体名错误或端口被防火墙拦截)"}

    sys_descr = decode_bytes_str(snmp_get_scalar(ip, community, OID_SYS_DESCR, port, version, timeout))
    sys_name = decode_bytes_str(snmp_get_scalar(ip, community, OID_SYS_NAME, port, version, timeout))
    sys_obj_id = decode_bytes_str(snmp_get_scalar(ip, community, OID_SYS_OBJECT_ID, port, version, timeout))
    sys_contact = decode_bytes_str(snmp_get_scalar(ip, community, OID_SYS_CONTACT, port, version, timeout))
    sys_loc = decode_bytes_str(snmp_get_scalar(ip, community, OID_SYS_LOCATION, port, version, timeout))

    # Base MAC from Bridge-MIB
    raw_base_mac = snmp_get_scalar(ip, community, OID_DOT1D_BASE_BRIDGE_ADDRESS, port, version, timeout)
    base_mac = format_mac_bytes(raw_base_mac)
    vendor = lookup_vendor(base_mac) if base_mac else "未知"

    return {
        "reachable": True,
        "latency_ms": latency_ms,
        "sys_name": sys_name or "未配置",
        "sys_descr": sys_descr or "未知",
        "sys_uptime": format_uptime(raw_uptime) if isinstance(raw_uptime, int) else "未知",
        "raw_uptime": raw_uptime,
        "sys_obj_id": sys_obj_id or "未知",
        "sys_contact": sys_contact or "未配置",
        "sys_location": sys_loc or "未配置",
        "base_mac": base_mac or "未获取 (非交换机或无 Bridge-MIB)",
        "vendor": vendor,
    }


def inspect_interfaces(ip: str, community: str, port: int = 161, version: str = "v2c", timeout: float = 1.0) -> List[Dict[str, Any]]:
    """Query IF-MIB to get all interfaces with speed, duplex, admin/oper status and counters."""
    if_indices = snmp_walk(ip, community, OID_IF_INDEX, port, version, timeout)
    if not if_indices:
        return []

    if_descrs = snmp_walk(ip, community, OID_IF_DESCR, port, version, timeout)
    if_names = snmp_walk(ip, community, OID_IF_NAME, port, version, timeout)
    if_types = snmp_walk(ip, community, OID_IF_TYPE, port, version, timeout)
    if_speeds = snmp_walk(ip, community, OID_IF_SPEED, port, version, timeout)
    if_high_speeds = snmp_walk(ip, community, OID_IF_HIGH_SPEED, port, version, timeout)
    if_admin_status = snmp_walk(ip, community, OID_IF_ADMIN_STATUS, port, version, timeout)
    if_oper_status = snmp_walk(ip, community, OID_IF_OPER_STATUS, port, version, timeout)
    if_in_octets = snmp_walk(ip, community, OID_IF_HC_IN_OCTETS, port, version, timeout)
    if not if_in_octets:
        if_in_octets = snmp_walk(ip, community, OID_IF_IN_OCTETS, port, version, timeout)
    if_out_octets = snmp_walk(ip, community, OID_IF_HC_OUT_OCTETS, port, version, timeout)
    if not if_out_octets:
        if_out_octets = snmp_walk(ip, community, OID_IF_OUT_OCTETS, port, version, timeout)

    interfaces: List[Dict[str, Any]] = []

    for oid, idx_val in if_indices.items():
        if not isinstance(idx_val, int):
            try:
                idx_val = int(oid.split(".")[-1])
            except Exception:
                continue

        idx = idx_val
        descr = decode_bytes_str(if_descrs.get(f"{OID_IF_DESCR}.{idx}", ""))
        name = decode_bytes_str(if_names.get(f"{OID_IF_NAME}.{idx}", ""))
        display_name = name if name else descr if descr else f"Port {idx}"

        itype = if_types.get(f"{OID_IF_TYPE}.{idx}", 0)
        admin = if_admin_status.get(f"{OID_IF_ADMIN_STATUS}.{idx}", 0)
        oper = if_oper_status.get(f"{OID_IF_OPER_STATUS}.{idx}", 0)

        # Speed: prefer ifHighSpeed (in Mbps), fallback to ifSpeed (in bps)
        high_speed = if_high_speeds.get(f"{OID_IF_HIGH_SPEED}.{idx}")
        standard_speed = if_speeds.get(f"{OID_IF_SPEED}.{idx}")
        speed_bps = 0
        if isinstance(high_speed, int) and high_speed > 0:
            speed_bps = high_speed * 1_000_000
        elif isinstance(standard_speed, int) and standard_speed > 0:
            speed_bps = standard_speed

        in_octets = if_in_octets.get(f"{OID_IF_HC_IN_OCTETS}.{idx}", if_in_octets.get(f"{OID_IF_IN_OCTETS}.{idx}", 0))
        out_octets = if_out_octets.get(f"{OID_IF_HC_OUT_OCTETS}.{idx}", if_out_octets.get(f"{OID_IF_OUT_OCTETS}.{idx}", 0))

        interfaces.append({
            "index": idx,
            "name": display_name,
            "descr": descr,
            "type": itype,
            "admin_status": "UP" if admin == 1 else "DOWN",
            "oper_status": "UP" if oper == 1 else "DOWN",
            "speed_bps": speed_bps,
            "speed_display": format_speed(speed_bps),
            "in_octets": in_octets if isinstance(in_octets, int) else 0,
            "out_octets": out_octets if isinstance(out_octets, int) else 0,
        })

    interfaces.sort(key=lambda x: x["index"])
    return interfaces


def inspect_lldp_neighbors(
    ip: str, community: str, port: int = 161, version: str = "v2c", timeout: float = 1.0
) -> List[Dict[str, Any]]:
    """Query LLDP-MIB and parse neighbor relationships."""
    loc_ports = snmp_walk(ip, community, OID_LLDP_LOC_PORT_DESC, port, version, timeout)
    if not loc_ports:
        loc_ports = snmp_walk(ip, community, OID_LLDP_LOC_PORT_ID, port, version, timeout)

    # Map loc_port_num -> display name
    local_port_map: Dict[int, str] = {}
    for oid, val in loc_ports.items():
        parts = oid.split(".")
        if parts:
            try:
                p_num = int(parts[-1])
                local_port_map[p_num] = decode_bytes_str(val)
            except Exception:
                pass

    rem_chassis = snmp_walk(ip, community, OID_LLDP_REM_CHASSIS_ID, port, version, timeout)
    rem_ports = snmp_walk(ip, community, OID_LLDP_REM_PORT_ID, port, version, timeout)
    rem_port_descs = snmp_walk(ip, community, OID_LLDP_REM_PORT_DESC, port, version, timeout)
    rem_sysnames = snmp_walk(ip, community, OID_LLDP_REM_SYS_NAME, port, version, timeout)
    rem_sysdescs = snmp_walk(ip, community, OID_LLDP_REM_SYS_DESC, port, version, timeout)
    rem_man_addrs = snmp_walk(ip, community, OID_LLDP_REM_MAN_ADDR, port, version, timeout)

    # Parse Management IPs from OID suffix: .locPortNum.remIndex.subtype.len.ip1.ip2.ip3.ip4
    man_ips: Dict[Tuple[int, int], str] = {}
    for oid in rem_man_addrs.keys():
        parts = oid.strip(".").split(".")
        if len(parts) >= 6:
            ip_candidate = ".".join(parts[-4:])
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_candidate):
                try:
                    loc_p = int(parts[-7])
                    rem_i = int(parts[-6])
                    man_ips[(loc_p, rem_i)] = ip_candidate
                except Exception:
                    pass

    neighbors: List[Dict[str, Any]] = []

    for oid, chassis_val in rem_chassis.items():
        parts = oid.strip(".").split(".")
        if len(parts) < 2:
            continue
        try:
            loc_port_num = int(parts[-2])
            rem_index = int(parts[-1])
        except Exception:
            continue

        chassis_str = format_mac_bytes(chassis_val)
        vendor = lookup_vendor(chassis_str)

        # Match remote port
        rem_port_id = ""
        for k, v in rem_ports.items():
            if k.endswith(f".{loc_port_num}.{rem_index}"):
                rem_port_id = decode_bytes_str(v)
                break

        rem_port_desc = ""
        for k, v in rem_port_descs.items():
            if k.endswith(f".{loc_port_num}.{rem_index}"):
                rem_port_desc = decode_bytes_str(v)
                break

        rem_sysname = ""
        for k, v in rem_sysnames.items():
            if k.endswith(f".{loc_port_num}.{rem_index}"):
                rem_sysname = decode_bytes_str(v)
                break

        rem_sysdesc = ""
        for k, v in rem_sysdescs.items():
            if k.endswith(f".{loc_port_num}.{rem_index}"):
                rem_sysdesc = decode_bytes_str(v)
                break

        mgmt_ip = man_ips.get((loc_port_num, rem_index), "")

        local_port_name = local_port_map.get(loc_port_num, f"Port {loc_port_num}")

        neighbors.append({
            "local_port_num": loc_port_num,
            "local_port": local_port_name,
            "rem_index": rem_index,
            "rem_chassis_id": chassis_str,
            "rem_vendor": vendor,
            "rem_sysname": rem_sysname or "未广播系统名",
            "rem_port": rem_port_id or rem_port_desc or f"RemPort {rem_index}",
            "rem_port_desc": rem_port_desc,
            "rem_mgmt_ip": mgmt_ip or "未广播管理IP",
            "rem_sysdesc": rem_sysdesc,
        })

    neighbors.sort(key=lambda x: x["local_port_num"])
    return neighbors


def inspect_fdb_table(
    ip: str, community: str, port: int = 161, version: str = "v2c", timeout: float = 1.0
) -> List[Dict[str, Any]]:
    """Query BRIDGE-MIB Forwarding Database (FDB / MAC table)."""
    # 1. BasePort -> IfIndex mapping
    base_port_map = snmp_walk(ip, community, OID_DOT1D_BASE_PORT_IF_INDEX, port, version, timeout)
    port_to_ifindex: Dict[int, int] = {}
    for oid, val in base_port_map.items():
        if isinstance(val, int):
            try:
                base_p = int(oid.split(".")[-1])
                port_to_ifindex[base_p] = val
            except Exception:
                pass

    # 2. FDB Port map: OID suffix has 6 decimal bytes of MAC
    fdb_ports = snmp_walk(ip, community, OID_DOT1D_TP_FDB_PORT, port, version, timeout)
    fdb_statuses = snmp_walk(ip, community, OID_DOT1D_TP_FDB_STATUS, port, version, timeout)

    entries: List[Dict[str, Any]] = []

    for oid, base_port in fdb_ports.items():
        if not isinstance(base_port, int) or base_port <= 0:
            continue

        parts = oid.split(".")
        if len(parts) < 6:
            continue
        try:
            mac_bytes = bytes([int(b) for b in parts[-6:]])
            mac_str = ":".join(f"{b:02X}" for b in mac_bytes)
        except Exception:
            continue

        status_val = fdb_statuses.get(f"{OID_DOT1D_TP_FDB_STATUS}.{'.'.join(parts[-6:])}", 3)
        # Status: 1=other, 2=invalid, 3=learned, 4=self, 5=mgmt
        status_desc = {1: "other", 2: "invalid", 3: "learned (动态学习)", 4: "self (本机)", 5: "mgmt"}.get(status_val, str(status_val))

        ifindex = port_to_ifindex.get(base_port, base_port)
        vendor = lookup_vendor(mac_str)

        entries.append({
            "mac": mac_str,
            "base_port": base_port,
            "if_index": ifindex,
            "status": status_desc,
            "vendor": vendor,
        })

    entries.sort(key=lambda x: (x["if_index"], x["mac"]))
    return entries
