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


def test_discover_edge_topology_scenario(monkeypatch):
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import discover_edge_topology

    init_db()
    with SessionLocal() as db:
        # Create Main Switch
        sw = Device(
            name="SW-Access-1",
            type="switch",
            ip_address="192.168.1.10",
            mac_address="00:11:22:AA:BB:CC",
            snmp_enabled=True,
            port_count=24,
        )
        # Port 5: Single Wired PC
        pc1 = Device(
            name="PC-Office-1",
            type="server",
            ip_address="192.168.1.51",
            mac_address="00:1A:2B:3C:4D:5E",
            snmp_enabled=False,
        )
        # Port 8: 2 Wired PCs (Hub)
        pc2 = Device(
            name="PC-Finance-1",
            type="server",
            ip_address="192.168.1.81",
            mac_address="18:66:DA:11:22:33",  # HP
            snmp_enabled=False,
        )
        pc3 = Device(
            name="PC-Finance-2",
            type="server",
            ip_address="192.168.1.82",
            mac_address="34:97:F6:44:55:66",  # Dell
            snmp_enabled=False,
        )
        # Port 12: AP
        ap1 = Device(
            name="AP-Meeting-Room",
            type="ap",
            ip_address="192.168.1.120",
            mac_address="74:05:A5:11:22:33",  # Ruijie
            snmp_enabled=False,
        )
        db.add_all([sw, pc1, pc2, pc3, ap1])
        db.commit()

        # Mock FDB for sw
        mock_fdb = [
            # Port 5: PC1
            {"local_port_num": 5, "local_port_name": "GigabitEthernet5", "learned_mac": "00:1A:2B:3C:4D:5E"},
            # Port 8: PC2, PC3 and an unmanaged device
            {"local_port_num": 8, "local_port_name": "GigabitEthernet8", "learned_mac": "18:66:DA:11:22:33"},
            {"local_port_num": 8, "local_port_name": "GigabitEthernet8", "learned_mac": "34:97:F6:44:55:66"},
            # Port 12: AP + 2 mobile phones with random MACs
            {"local_port_num": 12, "local_port_name": "GigabitEthernet12", "learned_mac": "74:05:A5:11:22:33"},
            {"local_port_num": 12, "local_port_name": "GigabitEthernet12", "learned_mac": "DA:A1:19:AA:BB:CC"},  # random
            {"local_port_num": 12, "local_port_name": "GigabitEthernet12", "learned_mac": "52:84:E2:DD:EE:FF"},  # random
        ]
        monkeypatch.setattr("app.services.lldp.get_device_fdb_table", lambda *args, **kwargs: mock_fdb)

        result = discover_edge_topology(db, switch_ids=[sw.id])

        # Assert Port 5 direct terminal
        assert len(result["direct_terminals"]) == 1
        dt = result["direct_terminals"][0]
        assert dt["switch_id"] == sw.id
        assert dt["port_num"] == 5
        assert dt["device_name"] == "PC-Office-1"

        # Assert Port 8 unmanaged hub
        assert len(result["unmanaged_hubs"]) == 1
        hub = result["unmanaged_hubs"][0]
        assert hub["switch_id"] == sw.id
        assert hub["port_num"] == 8
        assert hub["terminal_count"] == 2
        attached_ids = [d["device_id"] for d in hub["attached_devices"]]
        assert pc2.id in attached_ids
        assert pc3.id in attached_ids

        # Assert Port 12 AP cluster
        assert len(result["ap_clusters"]) == 1
        cluster = result["ap_clusters"][0]
        assert cluster["switch_id"] == sw.id
        assert cluster["port_num"] == 12
        assert cluster["ap_name"] == "AP-Meeting-Room"
        assert cluster["mobile_count"] >= 2

