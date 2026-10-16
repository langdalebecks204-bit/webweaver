from app.services.oui import normalize_mac, lookup_vendor


def test_normalize_mac():
    assert normalize_mac("00:11:22:33:44:55") == "00:11:22:33:44:55"
    assert normalize_mac("00-11-22-33-44-55") == "00:11:22:33:44:55"
    assert normalize_mac("0011.2233.4455") == "00:11:22:33:44:55"
    assert normalize_mac("001122334455") == "00:11:22:33:44:55"
    assert normalize_mac("48-2c-6a-aa-bb-cc") == "48:2C:6A:AA:BB:CC"
    assert normalize_mac("invalid_mac") is None
    assert normalize_mac("") is None
    assert normalize_mac(None) is None


def test_lookup_vendor():
    # Huawei
    assert lookup_vendor("70:79:90:11:22:33") == "Huawei"
    # H3C
    assert lookup_vendor("00:0F:E2:11:22:33") == "H3C"
    # Cisco
    assert lookup_vendor("00:00:0C:11:22:33") == "Cisco"
    # Ruijie
    assert lookup_vendor("00:1A:A9:11:22:33") == "Ruijie"
    # TP-Link
    assert lookup_vendor("50:BD:5F:11:22:33") == "TP-Link"
    # Hikvision
    assert lookup_vendor("44:19:B6:11:22:33") == "Hikvision"
    # Dahua
    assert lookup_vendor("3C:EF:8C:11:22:33") == "Dahua"
    # Apple
    assert lookup_vendor("48:2C:6A:11:22:33") == "Apple"
    # Xiaomi
    assert lookup_vendor("64:90:C1:11:22:33") == "Xiaomi"
    # Unknown
    assert lookup_vendor("FF:FF:FF:00:11:22") == "未知厂商"
    assert lookup_vendor(None) == "未知厂商"
