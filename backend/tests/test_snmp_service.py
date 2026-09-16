import time
from app.services.snmp import calculate_bandwidth, format_rate

def test_calculate_bandwidth_normal():
    # 100,000 bytes over 5 seconds = 20,000 Bps = 160,000 bps
    rate = calculate_bandwidth(prev_bytes=1000, curr_bytes=101000, time_delta_sec=5.0)
    assert rate == 160000.0

def test_calculate_bandwidth_zero_time():
    rate = calculate_bandwidth(prev_bytes=1000, curr_bytes=101000, time_delta_sec=0)
    assert rate == 0.0

def test_calculate_bandwidth_overflow():
    # 32-bit counter overflow (4294967295)
    max_32 = 4294967296
    prev = max_32 - 1000
    curr = 4000
    # diff = 1000 + 4000 = 5000 bytes in 1s = 40,000 bps
    rate = calculate_bandwidth(prev_bytes=prev, curr_bytes=curr, time_delta_sec=1.0, max_bytes=max_32)
    assert rate == 40000.0

def test_format_rate():
    assert format_rate(500) == "500 bps"
    assert format_rate(1500) == "1.50 Kbps"
    assert format_rate(2500000) == "2.50 Mbps"
    assert format_rate(1500000000) == "1.50 Gbps"


def test_get_switch_interfaces_fallback_without_ifdescr(monkeypatch):
    from app.services import snmp

    def mock_snmp_walk(ip, community, root_oid, port=161, version="v2c", timeout=1.5):
        if root_oid == snmp.OID_IF_DESCR:
            return {}  # Device does not implement ifDescr!
        elif root_oid == snmp.OID_IF_NAME:
            return {}
        elif root_oid == snmp.OID_IF_OPER_STATUS:
            return {
                f"{snmp.OID_IF_OPER_STATUS}.1": 1,
                f"{snmp.OID_IF_OPER_STATUS}.2": 2,
            }
        elif root_oid == snmp.OID_IF_SPEED:
            return {
                f"{snmp.OID_IF_SPEED}.1": 1000000000,
                f"{snmp.OID_IF_SPEED}.2": 0,
            }
        elif root_oid == snmp.OID_IF_HIGH_SPEED:
            return {
                f"{snmp.OID_IF_HIGH_SPEED}.1": 1000,
                f"{snmp.OID_IF_HIGH_SPEED}.2": 0,
            }
        elif root_oid == snmp.OID_IF_HC_IN_OCTETS:
            return {
                f"{snmp.OID_IF_HC_IN_OCTETS}.1": 100000,
                f"{snmp.OID_IF_HC_IN_OCTETS}.2": 0,
            }
        elif root_oid == snmp.OID_IF_HC_OUT_OCTETS:
            return {
                f"{snmp.OID_IF_HC_OUT_OCTETS}.1": 200000,
                f"{snmp.OID_IF_HC_OUT_OCTETS}.2": 0,
            }
        return {}

    monkeypatch.setattr(snmp, "snmp_walk", mock_snmp_walk)

    interfaces = snmp.get_switch_interfaces(device_id=99, ip="172.16.2.30")
    assert len(interfaces) == 2
    assert interfaces[0]["if_index"] == 1
    assert interfaces[0]["name"] == "Port1"
    assert interfaces[0]["status"] == "up"
    assert interfaces[0]["speed_mbps"] == 1000

    assert interfaces[1]["if_index"] == 2
    assert interfaces[1]["name"] == "Port2"
    assert interfaces[1]["status"] == "down"

