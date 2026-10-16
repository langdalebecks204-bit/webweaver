from app.services.lldp import parse_lldp_rem_table, match_remote_device, merge_lldp_links


def test_parse_lldp_rem_table():
    # Simulated SNMP walk results
    # locPortNum = 1, remIndex = 1
    # timeMark = 0
    rem_chassis = {
        "1.0.8802.1.1.2.1.4.1.1.5.0.1.1": b"\x70\x79\x90\x11\x22\x33",  # MAC: 70:79:90:11:22:33
    }
    rem_ports = {
        "1.0.8802.1.1.2.1.4.1.1.7.0.1.1": b"GigabitEthernet0/0/24",
    }
    rem_sysnames = {
        "1.0.8802.1.1.2.1.4.1.1.9.0.1.1": b"SW-Floor-2",
    }
    # RemManAddr OID ending: ... .0.1.1.1.4.192.168.1.2 (IPv4 192.168.1.2)
    rem_man_addrs = {
        "1.0.8802.1.1.2.1.4.2.1.3.0.1.1.1.4.192.168.1.2": 1,
    }
    # Local port descriptions
    loc_ports = {
        1: "GigabitEthernet0/0/1",
    }

    neighbors = parse_lldp_rem_table(
        rem_chassis=rem_chassis,
        rem_ports=rem_ports,
        rem_sysnames=rem_sysnames,
        rem_man_addrs=rem_man_addrs,
        loc_ports=loc_ports,
    )

    assert len(neighbors) == 1
    n = neighbors[0]
    assert n["local_port_num"] == 1
    assert n["local_port_name"] == "GigabitEthernet0/0/1"
    assert n["remote_chassis_id"] == "70:79:90:11:22:33"
    assert n["remote_port_id"] == "GigabitEthernet0/0/24"
    assert n["remote_sys_name"] == "SW-Floor-2"
    assert n["remote_man_ip"] == "192.168.1.2"


def test_match_remote_device():
    devices = [
        {"id": 1, "name": "Core-Switch", "ip_address": "192.168.1.1", "mac_address": "00:00:0C:01:02:03"},
        {"id": 2, "name": "SW-Floor-2", "ip_address": "192.168.1.2", "mac_address": "70:79:90:11:22:33"},
        {"id": 3, "name": "AP-Hall", "ip_address": "192.168.1.50", "mac_address": "50:BD:5F:11:22:33"},
    ]

    # Match by Management IP
    match1 = match_remote_device(
        remote_man_ip="192.168.1.2",
        remote_chassis_id="UNKNOWN",
        remote_sys_name="Random",
        devices=devices,
    )
    assert match1 is not None
    assert match1["id"] == 2

    # Match by Chassis MAC
    match2 = match_remote_device(
        remote_man_ip=None,
        remote_chassis_id="50:BD:5F:11:22:33",
        remote_sys_name="Random",
        devices=devices,
    )
    assert match2 is not None
    assert match2["id"] == 3

    # Match by SysName
    match3 = match_remote_device(
        remote_man_ip=None,
        remote_chassis_id="UNKNOWN",
        remote_sys_name="Core-Switch",
        devices=devices,
    )
    assert match3 is not None
    assert match3["id"] == 1


def test_merge_lldp_links():
    # SW1 (id: 1) sees SW2 (id: 2) on P1 -> P24
    # SW2 (id: 2) sees SW1 (id: 1) on P24 -> P1
    raw_observations = [
        {
            "local_device_id": 1,
            "local_device_name": "SW1",
            "local_port": "GigabitEthernet0/0/1",
            "remote_device_id": 2,
            "remote_device_name": "SW2",
            "remote_port": "GigabitEthernet0/0/24",
        },
        {
            "local_device_id": 2,
            "local_device_name": "SW2",
            "local_port": "GigabitEthernet0/0/24",
            "remote_device_id": 1,
            "remote_device_name": "SW1",
            "remote_port": "GigabitEthernet0/0/1",
        },
    ]

    links = merge_lldp_links(raw_observations)
    assert len(links) == 1
    link = links[0]
    assert link["is_bidirectional"] is True
    assert (
        (link["source_id"] == 1 and link["target_id"] == 2) or
        (link["source_id"] == 2 and link["target_id"] == 1)
    )


def test_apply_lldp_topology():
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.lldp import apply_lldp_topology

    init_db()
    with SessionLocal() as db:
        sw1 = Device(name="CoreSwitch", type="switch", port_count=24)
        sw2 = Device(name="AccessSwitch", type="switch", port_count=24)
        db.add_all([sw1, sw2])
        db.commit()

        links_to_apply = [
            {
                "source_id": sw1.id,
                "target_id": sw2.id,
                "source_port": "GigabitEthernet0/0/1",
                "target_port": "GigabitEthernet0/0/24",
            }
        ]

        res = apply_lldp_topology(db, links_to_apply, update_hierarchy=True)
        assert res["status"] == "ok"
        assert res["applied_count"] == 2

        db.refresh(sw1)
        db.refresh(sw2)
        assert "1" in sw1.port_bindings
        assert sw1.port_bindings["1"]["target_id"] == sw2.id
        assert "24" in sw2.port_bindings
        assert sw2.port_bindings["24"]["target_id"] == sw1.id
        # Hierarchy: sw2 becomes child of CoreSwitch
        assert sw2.parent_id == sw1.id


def test_get_device_fdb_table(monkeypatch):
    from app.services.lldp import get_device_fdb_table

    # Mock snmp_walk
    def mock_snmp_walk(ip, community, root_oid, *args, **kwargs):
        if "1.3.6.1.2.1.2.2.1.2" in root_oid:
            # loc_ports
            return {
                "1.3.6.1.2.1.2.2.1.2.1": b"MultiGigabitEthernet1",
                "1.3.6.1.2.1.2.2.1.2.24": b"MultiGigabitEthernet24",
            }
        elif "1.3.6.1.2.1.17.4.3.1.2" in root_oid:
            # FDB port table: MAC -> port
            return {
                # 84:94:59:1C:F7:B4 on port 1
                "1.3.6.1.2.1.17.4.3.1.2.132.148.89.28.247.180": 1,
                # 60:BE:B4:1A:E5:70 on port 24
                "1.3.6.1.2.1.17.4.3.1.2.96.190.180.26.229.112": 24,
            }
        return {}

    monkeypatch.setattr("app.services.lldp.snmp_walk", mock_snmp_walk)

    fdb = get_device_fdb_table("172.16.2.26", "public")
    assert len(fdb) == 2
    p1 = next(item for item in fdb if item["local_port_num"] == 1)
    assert p1["local_port_name"] == "MultiGigabitEthernet1"
    assert p1["learned_mac"] == "84:94:59:1C:F7:B4"

    p24 = next(item for item in fdb if item["local_port_num"] == 24)
    assert p24["local_port_name"] == "MultiGigabitEthernet24"
    assert p24["learned_mac"] == "60:BE:B4:1A:E5:70"


def test_discover_all_lldp_topology_with_fdb_fallback(monkeypatch):
    from app.database import SessionLocal, init_db
    from app.models import Device
    from app.services.lldp import discover_all_lldp_topology

    init_db()
    with SessionLocal() as db:
        # Create Main Switch (Whitebox without LLDP)
        sw_main = Device(
            name="ZX-SWTGW2224AS",
            type="switch",
            ip_address="172.16.2.26",
            mac_address="00:11:22:AA:BB:CC",
            snmp_enabled=True,
            port_count=24,
        )
        # Create Target Device (Router with MAC)
        ros_router = Device(
            name="MikroTik-Router",
            type="router",
            ip_address="172.16.2.1",
            mac_address="60:BE:B4:1A:E5:70",
            snmp_enabled=False,
            port_count=8,
        )
        db.add_all([sw_main, ros_router])
        db.commit()

        # Mock: LLDP returns empty, FDB returns MikroTik on port 24
        monkeypatch.setattr("app.services.lldp.get_device_lldp_neighbors", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            "app.services.lldp.get_device_fdb_table",
            lambda *args, **kwargs: [
                {
                    "local_port_num": 24,
                    "local_port_name": "MultiGigabitEthernet24",
                    "learned_mac": "60:BE:B4:1A:E5:70",
                },
                {
                    "local_port_num": 1,
                    "local_port_name": "MultiGigabitEthernet1",
                    "learned_mac": "84:94:59:1C:F7:B4",  # Hikvision unmanaged
                },
            ],
        )

        res = discover_all_lldp_topology(db)
        assert len(res["links"]) == 1
        link = res["links"][0]
        assert link["source_name"] == "ZX-SWTGW2224AS"
        assert link["source_port"] == "MultiGigabitEthernet24"
        assert link["target_name"] == "MikroTik-Router"

        # Check unmatched
        unmatched = res["unmatched_neighbors"]
        assert len(unmatched) >= 1
        hk = next((u for u in unmatched if "84:94:59" in u["remote_chassis_id"]), None)
        assert hk is not None
        assert hk["local_port"] == "MultiGigabitEthernet1"
        assert hk["remote_sys_name"] == "Hikvision"


