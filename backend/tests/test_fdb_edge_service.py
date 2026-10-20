import pytest
from app.services.fdb_edge import is_random_mac, is_mobile_oui

def test_is_random_mac():
    # Local bit set: 2nd hex is 2, 6, A, E
    assert is_random_mac("DA:A1:19:11:22:33") is True  # A
    assert is_random_mac("52:84:E2:44:55:66") is True  # 2
    assert is_random_mac("B6:12:34:56:78:9A") is True  # 6
    assert is_random_mac("FE:12:34:56:78:9A") is True  # E
    assert is_random_mac("da-a1-19-11-22-33") is True
    # Unicast globally unique (standard hardware MAC)
    assert is_random_mac("00:11:22:33:44:55") is False
    assert is_random_mac("84:94:59:1C:F7:B4") is False
    assert is_random_mac("60:BE:B4:1A:E5:70") is False
    assert is_random_mac("") is False
    assert is_random_mac(None) is False

def test_is_mobile_oui():
    assert is_mobile_oui("Apple") is True
    assert is_mobile_oui("Xiaomi Communications") is True
    assert is_mobile_oui("Huawei Device Co., Ltd.") is True
    assert is_mobile_oui("vivo Mobile") is True
    assert is_mobile_oui("OPPO Guangdong") is True
    assert is_mobile_oui("Honor Device") is True
    assert is_mobile_oui("Samsung Electronics (Mobile)") is True
    # Non-mobile vendors
    assert is_mobile_oui("Cisco Systems") is False
    assert is_mobile_oui("Hikvision") is False
    assert is_mobile_oui("TP-Link") is False
    assert is_mobile_oui("MikroTik") is False
    assert is_mobile_oui("") is False
    assert is_mobile_oui(None) is False
