import socket
import time
from typing import Any, Dict, List, Optional, Tuple

# Raw SNMP OID Constants for IF-MIB
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"

# In-memory traffic cache: (device_id, if_index) -> (timestamp, in_bytes, out_bytes)
_TRAFFIC_CACHE: Dict[Tuple[int, int], Tuple[float, int, int]] = {}


def calculate_bandwidth(
    prev_bytes: int,
    curr_bytes: int,
    time_delta_sec: float,
    max_bytes: int = 4294967296  # 2^32 for 32-bit counter
) -> float:
    """Calculate bitrate in bits per second (bps) between two counter readings."""
    if time_delta_sec <= 0:
        return 0.0

    if curr_bytes >= prev_bytes:
        diff_bytes = curr_bytes - prev_bytes
    else:
        # Counter overflow/wrap
        diff_bytes = (max_bytes - prev_bytes) + curr_bytes

    return (diff_bytes * 8.0) / time_delta_sec


def format_rate(rate_bps: float) -> str:
    """Format bps into human-readable string (bps, Kbps, Mbps, Gbps)."""
    if rate_bps < 1000:
        return f"{rate_bps:.0f} bps"
    elif rate_bps < 1_000_000:
        return f"{rate_bps / 1000:.2f} Kbps"
    elif rate_bps < 1_000_000_000:
        return f"{rate_bps / 1_000_000:.2f} Mbps"
    else:
        return f"{rate_bps / 1_000_000_000:.2f} Gbps"


def encode_asn1_length(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    elif length < 256:
        return bytes([0x81, length])
    elif length < 65536:
        return bytes([0x82, length >> 8, length & 0xFF])
    raise ValueError("Length too long")


def encode_oid(oid_str: str) -> bytes:
    parts = [int(p) for p in oid_str.strip(".").split(".")]
    if len(parts) < 2:
        raise ValueError("Invalid OID")
    encoded = bytes([parts[0] * 40 + parts[1]])
    for sub in parts[2:]:
        if sub == 0:
            encoded += b"\x00"
        else:
            sub_bytes = []
            while sub > 0:
                sub_bytes.append((sub & 0x7F) | 0x80)
                sub >>= 7
            sub_bytes[0] &= 0x7F  # last byte has MSB 0
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

    if tag == 0x30:  # SEQUENCE
        sub_off = next_off
        elements = []
        while sub_off < end_off:
            _, val, sub_off = decode_asn1(data, sub_off)
            elements.append(val)
        return tag, elements, end_off
    elif tag in (0x02, 0x41, 0x42):  # INTEGER / Counter32 / Gauge32
        val = int.from_bytes(val_data, byteorder="big", signed=False)
        return tag, val, end_off
    elif tag == 0x46:  # Counter64
        val = int.from_bytes(val_data, byteorder="big", signed=False)
        return tag, val, end_off
    elif tag == 0x04:  # OCTET STRING
        return tag, val_data, end_off
    elif tag == 0x06:  # OBJECT IDENTIFIER
        # Parse OID
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


def build_snmp_getnext_packet(community: str, oid_str: str, request_id: int = 100, version: str = "v2c") -> bytes:
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
        + b"\x05\x00"  # NULL
    )
    varbind_list = b"\x30" + encode_asn1_length(len(varbind)) + varbind

    req_id_bytes = request_id.to_bytes(4, byteorder="big")
    pdu_contents = (
        b"\x02\x04" + req_id_bytes + b"\x02\x01\x00\x02\x01\x00" + varbind_list
    )
    pdu = b"\xa1" + encode_asn1_length(len(pdu_contents)) + pdu_contents  # 0xa1 = GetNextRequest

    message = b"\x30" + encode_asn1_length(len(ver_bytes) + len(comm_asn1) + len(pdu)) + ver_bytes + comm_asn1 + pdu
    return message


def snmp_walk(ip: str, community: str, root_oid: str, port: int = 161, version: str = "v2c", timeout: float = 1.5) -> Dict[str, Any]:
    results = {}
    curr_oid = root_oid
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    req_id = 1
    try:
        while True:
            packet = build_snmp_getnext_packet(community, curr_oid, request_id=req_id, version=version)
            sock.sendto(packet, (ip, port))
            data, _ = sock.recvfrom(4096)
            req_id += 1

            _, msg_el, _ = decode_asn1(data)
            if not isinstance(msg_el, list) or len(msg_el) < 3:
                break
            pdu_el = msg_el[2]
            if not isinstance(pdu_el, list) or len(pdu_el) < 4:
                break
            varbind_list = pdu_el[3]
            if not isinstance(varbind_list, list) or not varbind_list:
                break
            first_vb = varbind_list[0]
            if not isinstance(first_vb, list) or len(first_vb) < 2:
                break
            
            returned_oid = first_vb[0]
            val = first_vb[1]

            if not isinstance(returned_oid, str) or not returned_oid.startswith(root_oid + "."):
                break

            results[returned_oid] = val
            curr_oid = returned_oid
            if len(results) > 200:  # safety bound
                break
    except Exception:
        pass
    finally:
        sock.close()

    return results


def get_switch_interfaces(
    device_id: int,
    ip: str,
    community: str = "public",
    port: int = 161,
    version: str = "v2c",
    timeout: float = 1.5
) -> List[Dict[str, Any]]:
    """Walk IF-MIB and return status and real-time bandwidth for all interfaces."""
    # 1. Walk descriptions and status
    descrs = snmp_walk(ip, community, OID_IF_DESCR, port, version, timeout)
    statuses = snmp_walk(ip, community, OID_IF_OPER_STATUS, port, version, timeout)
    speeds = snmp_walk(ip, community, OID_IF_SPEED, port, version, timeout)
    high_speeds = snmp_walk(ip, community, OID_IF_HIGH_SPEED, port, version, timeout)
    in_octets = snmp_walk(ip, community, OID_IF_HC_IN_OCTETS, port, version, timeout)
    if not in_octets:
        in_octets = snmp_walk(ip, community, OID_IF_IN_OCTETS, port, version, timeout)
        is_64bit = False
    else:
        is_64bit = True

    out_octets = snmp_walk(ip, community, OID_IF_HC_OUT_OCTETS, port, version, timeout)
    if not out_octets:
        out_octets = snmp_walk(ip, community, OID_IF_OUT_OCTETS, port, version, timeout)

    now = time.time()
    interfaces = []

    # Map by index suffix
    indexes = set()
    for oid in descrs.keys():
        idx = int(oid.split(".")[-1])
        indexes.add(idx)

    for idx in sorted(indexes):
        descr_val = descrs.get(f"{OID_IF_DESCR}.{idx}", b"")
        if isinstance(descr_val, bytes):
            name = descr_val.decode("utf-8", errors="ignore").strip()
        else:
            name = str(descr_val)

        if not name:
            name = f"Port{idx}"

        stat_val = statuses.get(f"{OID_IF_OPER_STATUS}.{idx}", 2)
        status_str = "up" if stat_val == 1 else "down"

        # Speed
        high_spd = high_speeds.get(f"{OID_IF_HIGH_SPEED}.{idx}")
        if high_spd and isinstance(high_spd, int) and high_spd > 0:
            speed_mbps = high_spd
        else:
            spd = speeds.get(f"{OID_IF_SPEED}.{idx}", 0)
            speed_mbps = (spd // 1_000_000) if isinstance(spd, int) else 0

        # Octets & Traffic calculation
        curr_in = in_octets.get(f"{OID_IF_HC_IN_OCTETS if is_64bit else OID_IF_IN_OCTETS}.{idx}", 0)
        curr_out = out_octets.get(f"{OID_IF_HC_OUT_OCTETS if is_64bit else OID_IF_OUT_OCTETS}.{idx}", 0)
        if not isinstance(curr_in, int):
            curr_in = 0
        if not isinstance(curr_out, int):
            curr_out = 0

        cache_key = (device_id, idx)
        in_rate_bps = 0.0
        out_rate_bps = 0.0

        if cache_key in _TRAFFIC_CACHE:
            prev_time, prev_in, prev_out = _TRAFFIC_CACHE[cache_key]
            time_delta = now - prev_time
            max_val = (2**64) if is_64bit else (2**32)
            in_rate_bps = calculate_bandwidth(prev_in, curr_in, time_delta, max_val)
            out_rate_bps = calculate_bandwidth(prev_out, curr_out, time_delta, max_val)

        _TRAFFIC_CACHE[cache_key] = (now, curr_in, curr_out)

        interfaces.append({
            "if_index": idx,
            "name": name,
            "status": status_str,
            "speed_mbps": speed_mbps,
            "in_rate_bps": in_rate_bps,
            "out_rate_bps": out_rate_bps,
            "in_rate_text": format_rate(in_rate_bps),
            "out_rate_text": format_rate(out_rate_bps),
        })

    return interfaces
