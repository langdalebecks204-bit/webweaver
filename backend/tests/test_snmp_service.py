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
