from app.services.arp import parse_snmp_arp_entries, parse_windows_arp_output, parse_linux_arp_output


def test_parse_snmp_arp_entries():
    # OID: 1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ip>
    # Value: 6 bytes MAC
    phys_dict = {
        "1.3.6.1.2.1.4.22.1.2.5.192.168.1.100": b"\x70\x79\x90\xaa\xbb\xcc",
        "1.3.6.1.2.1.4.22.1.2.5.192.168.1.101": b"\x00\x0f\xe2\x11\x22\x33",
        "1.3.6.1.2.1.4.22.1.2.2.10.0.0.1": b"\x00\x00\x0c\x99\x88\x77",
    }
    if_names = {5: "GigabitEthernet0/5", 2: "Vlan-interface1"}
    entries = parse_snmp_arp_entries(phys_dict, if_names)

    assert len(entries) == 3
    # Check entry 1
    e1 = next(e for e in entries if e["ip"] == "192.168.1.100")
    assert e1["mac"] == "70:79:90:AA:BB:CC"
    assert e1["vendor"] == "Huawei"
    assert e1["if_index"] == 5
    assert e1["if_name"] == "GigabitEthernet0/5"

    # Check entry 2
    e2 = next(e for e in entries if e["ip"] == "192.168.1.101")
    assert e2["mac"] == "00:0F:E2:11:22:33"
    assert e2["vendor"] == "H3C"

    # Check entry 3
    e3 = next(e for e in entries if e["ip"] == "10.0.0.1")
    assert e3["mac"] == "00:00:0C:99:88:77"
    assert e3["vendor"] == "Cisco"


def test_parse_windows_arp_output():
    sample_win_output = """
接口: 192.168.1.20 --- 0x12
  Internet 地址         物理地址              类型
  192.168.1.1           70-79-90-12-34-56     动态
  192.168.1.254         ff-ff-ff-ff-ff-ff     静态
  192.168.1.88          00-1a-a9-78-90-ab     动态
"""
    entries = parse_windows_arp_output(sample_win_output)
    # Ignore broadcast FF-FF-FF-FF-FF-FF
    assert len(entries) == 2
    assert entries[0]["ip"] == "192.168.1.1"
    assert entries[0]["mac"] == "70:79:90:12:34:56"
    assert entries[0]["vendor"] == "Huawei"
    assert entries[1]["ip"] == "192.168.1.88"
    assert entries[1]["mac"] == "00:1A:A9:78:90:AB"
    assert entries[1]["vendor"] == "Ruijie"


def test_parse_linux_arp_output():
    sample_proc_arp = """IP address       HW type     Flags       HW address            Mask     Device
192.168.1.1      0x1         0x2         70:79:90:12:34:56     *        eth0
192.168.1.55     0x1         0x2         48:2c:6a:11:22:33     *        eth0
"""
    entries = parse_linux_arp_output(sample_proc_arp)
    assert len(entries) == 2
    assert entries[0]["ip"] == "192.168.1.1"
    assert entries[0]["mac"] == "70:79:90:12:34:56"
    assert entries[0]["vendor"] == "Huawei"
    assert entries[1]["ip"] == "192.168.1.55"
    assert entries[1]["mac"] == "48:2C:6A:11:22:33"
    assert entries[1]["vendor"] == "Apple"
