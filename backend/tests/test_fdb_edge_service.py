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


def test_apply_edge_topology_creates_hub_and_links():
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import apply_edge_topology

    init_db()
    with SessionLocal() as db:
        sw = Device(name="SW-Apply-Test", type="switch", port_count=24)
        c1 = Device(name="Client-Direct", type="server")
        c2 = Device(name="Client-Hub-1", type="server")
        c3 = Device(name="Client-Hub-2", type="server")
        db.add_all([sw, c1, c2, c3])
        db.commit()

        direct_terminals = [
            {"device_id": c1.id, "switch_id": sw.id, "port_num": 3, "port_name": "GE3"}
        ]
        hubs_to_create = [
            {
                "name": "财务室桌下5口交换机",
                "switch_id": sw.id,
                "port_num": 8,
                "port_name": "GE8",
                "device_ids": [c2.id, c3.id],
                "unregistered_macs": ["68:D7:9A:11:22:33"],
            }
        ]

        result = apply_edge_topology(db, direct_terminals, hubs_to_create)
        assert result["applied_direct_count"] == 1
        assert result["created_hubs_count"] == 1

        # Check c1 parent and switch port 3
        db.refresh(c1)
        db.refresh(sw)
        assert c1.parent_id == sw.id
        assert sw.port_bindings is not None
        assert str(sw.port_bindings["3"]["target_id"]) == str(c1.id)

        # Check Hub creation
        hub = db.query(Device).filter_by(name="财务室桌下5口交换机").first()
        assert hub is not None
        assert hub.is_virtual is True
        assert hub.type == "unmanaged_switch"
        assert hub.parent_id == sw.id
        assert str(sw.port_bindings["8"]["target_id"]) == str(hub.id)

        # Check c2, c3 reparented to Hub
        db.refresh(c2)
        db.refresh(c3)
        assert c2.parent_id == hub.id
        assert c3.parent_id == hub.id

        # Check unregistered device enrolled under Hub
        unreg = db.query(Device).filter_by(mac_address="68:D7:9A:11:22:33").first()
        assert unreg is not None
        assert unreg.parent_id == hub.id


def test_apply_edge_topology_unregistered_direct_and_backfill():
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import apply_edge_topology

    init_db()
    with SessionLocal() as db:
        sw = Device(name="SW-Backfill-Test", type="switch", port_count=24)
        existing_dev = Device(name="Legacy-PC", type="server", ip_address=None, mac_address=None)
        db.add_all([sw, existing_dev])
        db.commit()

        direct_terminals = [
            # 1. Existing device with missing MAC & IP -> backfill
            {
                "device_id": existing_dev.id,
                "switch_id": sw.id,
                "port_num": 1,
                "port_name": "GE1",
                "mac": "11:22:33:44:55:66",
                "ip_address": "192.168.1.101",
            },
            # 2. Brand new direct terminal with IP -> auto create named by IP
            {
                "device_id": None,
                "switch_id": sw.id,
                "port_num": 2,
                "port_name": "GE2",
                "mac": "22:33:44:55:66:77",
                "ip_address": "192.168.1.102",
                "device_name": None,
            },
            # 3. Brand new direct terminal without IP -> auto create named by MAC
            {
                "device_id": None,
                "switch_id": sw.id,
                "port_num": 3,
                "port_name": "GE3",
                "mac": "33:44:55:66:77:88",
                "ip_address": None,
                "device_name": None,
            },
        ]

        hubs_to_create = [
            {
                "name": "测试分线盒",
                "switch_id": sw.id,
                "port_num": 10,
                "port_name": "GE10",
                "device_ids": [],
                "unregistered_macs": [
                    {"mac": "55:66:77:88:99:AA", "ip": "192.168.1.150", "name": None},
                    {"mac": "66:77:88:99:AA:BB", "ip": None, "name": None},
                ],
            }
        ]

        result = apply_edge_topology(db, direct_terminals, hubs_to_create)
        assert result["applied_direct_count"] == 3
        assert result["created_hubs_count"] == 1

        # 1. Verify existing device backfilled
        db.refresh(existing_dev)
        assert existing_dev.parent_id == sw.id
        assert existing_dev.mac_address == "11:22:33:44:55:66"
        assert existing_dev.ip_address == "192.168.1.101"

        # 2. Verify direct terminal with IP
        d2 = db.query(Device).filter_by(mac_address="22:33:44:55:66:77").first()
        assert d2 is not None
        assert d2.name == "终端 (192.168.1.102)"
        assert d2.ip_address == "192.168.1.102"
        assert d2.parent_id == sw.id

        # 3. Verify direct terminal without IP (should include vendor + MAC)
        d3 = db.query(Device).filter_by(mac_address="33:44:55:66:77:88").first()
        assert d3 is not None
        assert d3.name == "终端 (未知厂商33:44:55:66:77:88)"
        assert d3.ip_address is None
        assert d3.parent_id == sw.id

        # 4. Verify hub terminals
        hub = db.query(Device).filter_by(name="测试分线盒").first()
        assert hub is not None
        ht1 = db.query(Device).filter_by(mac_address="55:66:77:88:99:AA").first()
        assert ht1 is not None
        assert ht1.name == "终端 (192.168.1.150)"
        assert ht1.ip_address == "192.168.1.150"
        assert ht1.parent_id == hub.id

        ht2 = db.query(Device).filter_by(mac_address="66:77:88:99:AA:BB").first()
        assert ht2 is not None
        assert ht2.name == "终端 (未知厂商66:77:88:99:AA:BB)"
        assert ht2.ip_address is None
        assert ht2.parent_id == hub.id


def test_format_terminal_default_name():
    from app.services.fdb_edge import format_terminal_default_name

    # With IP
    assert format_terminal_default_name("C8:A3:62:DF:93:0B", ip="192.168.1.50") == "终端 (192.168.1.50)"
    # Without IP, unknown vendor
    assert format_terminal_default_name("C8:A3:62:DF:93:0B", ip=None, vendor="未知厂商") == "终端 (未知厂商C8:A3:62:DF:93:0B)"
    assert format_terminal_default_name("C8:A3:62:DF:93:0B", ip=None, vendor=None) == "终端 (未知厂商C8:A3:62:DF:93:0B)"
    # Without IP, Chinese vendor
    assert format_terminal_default_name("C8:A3:62:DF:93:0B", ip=None, vendor="华为") == "终端 (华为C8:A3:62:DF:93:0B)"
    # Without IP, English vendor
    assert format_terminal_default_name("C8:A3:62:DF:93:0B", ip=None, vendor="Apple") == "终端 (Apple C8:A3:62:DF:93:0B)"


def test_discover_and_apply_with_existing_unmanaged_switch(monkeypatch):
    """When a switch port already has an unmanaged switch configured:
    1. discover_edge_topology must not treat 1 learned MAC as direct_terminal;
       it must recognize the existing unmanaged switch and put the terminal under it.
    2. apply_edge_topology must NOT overwrite the switch's port binding, and must
       subsume the terminals under the existing unmanaged switch without creating a duplicate hub.
    """
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import discover_edge_topology, apply_edge_topology

    init_db()
    with SessionLocal() as db:
        # Create core/main switch
        sw = Device(
            name="Main-Switch-24P",
            type="switch",
            ip_address="192.168.1.1",
            mac_address="00:11:22:33:44:55",
            snmp_enabled=True,
            port_count=24,
        )
        db.add(sw)
        db.commit()

        # Create subordinate unmanaged dumb switch on Port 5
        dumb_sw = Device(
            name="二楼弱电箱5口D-Link",
            type="unmanaged_switch",
            parent_id=sw.id,
            port_count=5,
            uplink_port=1,
            is_virtual=True,
            status="online",
        )
        db.add(dumb_sw)
        db.commit()

        # Set Port 5 on Main Switch to point to dumb_sw
        sw.port_bindings = {
            "5": {
                "target_id": dumb_sw.id,
                "target_port": 1,
                "type": "downlink",
                "rate": "1000M",
            }
        }
        db.commit()

        # Device A is already registered in DB
        dev_a = Device(
            name="财务电脑A",
            type="server",
            ip_address="192.168.1.105",
            mac_address="70:85:C2:11:22:33",
            parent_id=sw.id,  # was mistakenly under sw.id
        )
        db.add(dev_a)
        db.commit()

        # Mock FDB: Port 5 only learns 1 MAC (dev_a)
        mock_fdb = [
            {"local_port_num": 5, "local_port_name": "GigabitEthernet5", "learned_mac": "70:85:C2:11:22:33"},
        ]
        monkeypatch.setattr("app.services.lldp.get_device_fdb_table", lambda *args, **kwargs: mock_fdb)

        # 1. Test discover_edge_topology
        res = discover_edge_topology(db, switch_ids=[sw.id])
        # Port 5 must NOT be in direct_terminals
        assert len(res["direct_terminals"]) == 0
        # Port 5 MUST be in unmanaged_hubs
        assert len(res["unmanaged_hubs"]) == 1
        hub = res["unmanaged_hubs"][0]
        assert hub["switch_id"] == sw.id
        assert hub["port_num"] == 5
        assert hub["is_existing"] is True
        assert hub["hub_id"] == dumb_sw.id
        assert hub["suggested_name"] == "二楼弱电箱5口D-Link"
        assert len(hub["attached_devices"]) == 1
        assert hub["attached_devices"][0]["device_id"] == dev_a.id

        # 2. Test apply_edge_topology
        hubs_to_apply = [
            {
                "name": hub["suggested_name"],
                "switch_id": sw.id,
                "port_num": 5,
                "hub_id": dumb_sw.id,
                "device_ids": [dev_a.id],
                "unregistered_macs": [
                    {"mac": "88:25:93:44:55:66", "ip": "192.168.1.106", "name": "财务电脑B"}
                ],
            }
        ]

        apply_res = apply_edge_topology(db, direct_terminals=[], hubs_to_create=hubs_to_apply)
        assert apply_res["reused_hubs_count"] == 1
        assert apply_res["created_hubs_count"] == 0

        # Verify database state:
        db.refresh(sw)
        db.refresh(dumb_sw)
        db.refresh(dev_a)

        # Switch port 5 binding MUST still point to dumb_sw!
        assert sw.port_bindings["5"]["target_id"] == dumb_sw.id
        # dev_a MUST be reparented under dumb_sw!
        assert dev_a.parent_id == dumb_sw.id

        # Newly registered dev_b MUST also be under dumb_sw!
        dev_b = db.query(Device).filter_by(mac_address="88:25:93:44:55:66").first()
        assert dev_b is not None
        assert dev_b.parent_id == dumb_sw.id
        assert dev_b.name == "财务电脑B"


def test_apply_direct_terminal_safeguards_existing_hub():
    """If a direct terminal was sent for a port that has an unmanaged switch,
    it must NOT overwrite switch port_bindings, and must reparent under the unmanaged switch.
    """
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import apply_edge_topology

    init_db()
    with SessionLocal() as db:
        sw = Device(name="SW-Safe-Test", type="switch", port_count=24)
        db.add(sw)
        db.commit()

        hub = Device(name="Existing-Hub", type="unmanaged_switch", parent_id=sw.id, port_count=8)
        db.add(hub)
        db.commit()

        sw.port_bindings = {"3": {"target_id": hub.id, "type": "downlink"}}
        db.commit()

        client = Device(name="PC-Under-Hub", type="server")
        db.add(client)
        db.commit()

        # Send as direct terminal on Port 3
        dt = [{"device_id": client.id, "switch_id": sw.id, "port_num": 3, "port_name": "GE3"}]
        res = apply_edge_topology(db, direct_terminals=dt, hubs_to_create=[])
        assert res["applied_direct_count"] == 1

        db.refresh(sw)
        db.refresh(client)
        # Port binding MUST still point to hub, NOT client!
        assert sw.port_bindings["3"]["target_id"] == hub.id
        # Client MUST be placed under hub!
        assert client.parent_id == hub.id


def test_repeated_fdb_apply_does_not_create_duplicates():
    """Testing Problem 1: Repeated '一键添加' must be idempotent and not create duplicate devices."""
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import apply_edge_topology

    init_db()
    with SessionLocal() as db:
        sw = Device(name="SW-Repeat-Test", type="switch", port_count=24)
        db.add(sw)
        db.commit()

        direct_terminals = [
            {
                "switch_id": sw.id,
                "port_num": 1,
                "port_name": "GE1",
                "mac": "1A:2B:3C:4D:5E:6F",
                "ip_address": "192.168.1.101",
                "device_id": None,
                "device_name": "PC-Direct-1",
            }
        ]
        hubs_to_create = [
            {
                "name": "走廊分线交换机",
                "switch_id": sw.id,
                "port_num": 2,
                "port_name": "GE2",
                "device_ids": [],
                "unregistered_macs": [
                    {"mac": "2A:3B:4C:5D:6E:7F", "ip": "192.168.1.102", "name": "PC-Hub-1"},
                    {"mac": "3A:4B:5C:6D:7E:8F", "ip": "192.168.1.103", "name": "PC-Hub-2"},
                ],
            }
        ]

        # 1st Application
        res1 = apply_edge_topology(db, direct_terminals, hubs_to_create)
        assert res1["applied_direct_count"] == 1
        assert res1["created_hubs_count"] == 1

        total_devs_1 = db.query(Device).count()

        # 2nd Application with identical payload (simulating user clicking apply again)
        res2 = apply_edge_topology(db, direct_terminals, hubs_to_create)
        assert res2["applied_direct_count"] == 1
        assert res2["reused_hubs_count"] == 1
        assert res2["created_hubs_count"] == 0

        total_devs_2 = db.query(Device).count()
        # Total device count in database MUST be identical (no duplicate rows created!)
        assert total_devs_1 == total_devs_2

        # Check unique MAC counts
        mac1 = db.query(Device).filter_by(mac_address="1A:2B:3C:4D:5E:6F").all()
        assert len(mac1) == 1
        mac2 = db.query(Device).filter_by(mac_address="2A:3B:4C:5D:6E:7F").all()
        assert len(mac2) == 1
        mac3 = db.query(Device).filter_by(mac_address="3A:4B:5C:6D:7E:8F").all()
        assert len(mac3) == 1


def test_multilevel_unmanaged_switch_hierarchy_preserved(monkeypatch):
    """Testing Problem 2: When devices are organized under multi-level unmanaged switches:
    SW -> Hub1 -> Hub2 -> PC1
    SW -> Hub1 -> PC2
    1. discover_edge_topology must recognize Hub1 as existing hub, and mark both PC1 & PC2 as already_under_hub.
    2. Even if only PC1 is learned (1 MAC), it must NOT be turned into a direct terminal of SW.
    3. apply_edge_topology must NOT flatten PC1's parent to Hub1 or SW, preserving Hub2 -> PC1!
    """
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.fdb_edge import discover_edge_topology, apply_edge_topology

    init_db()
    with SessionLocal() as db:
        # 1. Main Switch
        sw = Device(name="SW-Core", type="switch", ip_address="192.168.1.1", port_count=24, snmp_enabled=True)
        db.add(sw)
        db.commit()

        # 2. Level 1 Unmanaged Switch
        hub1 = Device(name="弱电箱一级傻瓜交换机", type="unmanaged_switch", parent_id=sw.id, is_virtual=True)
        db.add(hub1)
        db.commit()

        # Port 4 points to Hub1
        sw.port_bindings = {"4": {"target_id": hub1.id, "target_port": 1, "type": "downlink"}}
        db.commit()

        # 3. Level 2 Unmanaged Switch
        hub2 = Device(name="办公区二级傻瓜交换机", type="unmanaged_switch", parent_id=hub1.id, is_virtual=True)
        db.add(hub2)
        db.commit()

        # 4. PC1 under Level 2 (Hub2)
        pc1 = Device(name="开发电脑-1", type="server", ip_address="192.168.1.201", mac_address="AA:11:22:33:44:01", parent_id=hub2.id)
        # 5. PC2 under Level 1 (Hub1)
        pc2 = Device(name="打印机-1", type="server", ip_address="192.168.1.202", mac_address="AA:11:22:33:44:02", parent_id=hub1.id)
        db.add_all([pc1, pc2])
        db.commit()

        # Test Case A: Both PC1 and PC2 learned on port 4
        mock_fdb = [
            {"local_port_num": 4, "local_port_name": "GE4", "learned_mac": "AA:11:22:33:44:01"},
            {"local_port_num": 4, "local_port_name": "GE4", "learned_mac": "AA:11:22:33:44:02"},
        ]
        monkeypatch.setattr("app.services.lldp.get_device_fdb_table", lambda *args, **kwargs: mock_fdb)

        disc = discover_edge_topology(db, switch_ids=[sw.id])
        assert len(disc["direct_terminals"]) == 0
        assert len(disc["unmanaged_hubs"]) == 1

        h_info = disc["unmanaged_hubs"][0]
        assert h_info["hub_id"] == hub1.id
        assert h_info["is_existing"] is True

        att = {d["device_id"]: d for d in h_info["attached_devices"]}
        assert pc1.id in att
        assert pc2.id in att
        # Both must be identified as already under this hub branch!
        assert att[pc1.id]["already_under_hub"] is True
        assert att[pc2.id]["already_under_hub"] is True

        # Apply edge topology
        hubs_apply = [
            {
                "name": h_info["suggested_name"],
                "switch_id": sw.id,
                "port_num": 4,
                "hub_id": hub1.id,
                "device_ids": [pc1.id, pc2.id],
                "unregistered_macs": [],
            }
        ]
        apply_edge_topology(db, direct_terminals=[], hubs_to_create=hubs_apply)

        db.refresh(pc1)
        db.refresh(pc2)
        # CRITICAL VERIFICATION:
        # PC1 MUST REMAIN under Hub2 (NOT Hub1, NOT SW)!
        assert pc1.parent_id == hub2.id
        # PC2 remains under Hub1
        assert pc2.parent_id == hub1.id

        # Test Case B: Single MAC active (only PC1 on port 4)
        mock_fdb_single = [
            {"local_port_num": 4, "local_port_name": "GE4", "learned_mac": "AA:11:22:33:44:01"},
        ]
        monkeypatch.setattr("app.services.lldp.get_device_fdb_table", lambda *args, **kwargs: mock_fdb_single)

        disc_single = discover_edge_topology(db, switch_ids=[sw.id])
        # Even with single MAC, it MUST NOT be classified as direct_terminals!
        assert len(disc_single["direct_terminals"]) == 0
        assert len(disc_single["unmanaged_hubs"]) == 1

        # Even if someone maliciously calls apply with PC1 as a direct terminal on Port 4:
        dt_malicious = [{"device_id": pc1.id, "switch_id": sw.id, "port_num": 4, "port_name": "GE4"}]
        apply_edge_topology(db, direct_terminals=dt_malicious, hubs_to_create=[])

        db.refresh(pc1)
        db.refresh(sw)
        # PC1's parent MUST STILL NOT be hijacked to SW!
        assert pc1.parent_id == hub2.id
        # Port 4 binding MUST STILL point to Hub1, NOT pc1!
        assert sw.port_bindings["4"]["target_id"] == hub1.id





