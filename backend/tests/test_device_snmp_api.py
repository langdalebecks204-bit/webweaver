def test_get_device_snmp_interfaces_not_found(client, admin_headers):
    resp = client.get("/api/devices/99999/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 404

def test_get_device_snmp_interfaces_not_switch(client, admin_headers):
    # Create group device
    create_resp = client.post("/api/devices", json={"name": "Group Dev", "type": "group"}, headers=admin_headers)
    dev_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{dev_id}/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 400
    assert "not a switch" in resp.json()["detail"]

def test_get_device_snmp_interfaces_no_ip(client, admin_headers):
    # Create switch without IP
    payload = {
        "name": "Switch No IP",
        "type": "switch",
        "ip_address": None
    }
    create_resp = client.post("/api/devices", json=payload, headers=admin_headers)
    dev_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{dev_id}/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 400
    assert "IP address" in resp.json()["detail"]


def test_get_device_snmp_interfaces_snmp_disabled(client, admin_headers):
    payload = {
        "name": "Router SNMP Disabled",
        "type": "router",
        "ip_address": "192.168.1.1",
        "snmp_enabled": False,
    }
    create_resp = client.post("/api/devices", json=payload, headers=admin_headers)
    dev_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{dev_id}/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 400
    assert "SNMP is disabled" in resp.json()["detail"]


def test_get_device_snmp_interfaces_router_no_ip(client, admin_headers):
    payload = {
        "name": "Router No IP",
        "type": "router",
        "ip_address": None,
    }
    create_resp = client.post("/api/devices", json=payload, headers=admin_headers)
    dev_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{dev_id}/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 400
    assert "IP address" in resp.json()["detail"]


def test_get_device_snmp_interfaces_with_port_bindings(client, admin_headers, monkeypatch):
    from unittest.mock import MagicMock

    # Create target device
    target = client.post("/api/devices", json={"name": "CoreRouter", "type": "router", "ip_address": "10.0.0.1"}, headers=admin_headers).json()

    # Create switch with bindings
    payload = {
        "name": "Switch With Bindings",
        "type": "switch",
        "ip_address": "10.0.0.2",
        "port_count": 8,
        "snmp_enabled": True,
        "port_bindings": {
            "1": {"target_id": target["id"], "type": "uplink", "description": "Trunk Link"},
            "2": {"target_id": None, "type": "downlink", "description": "ISP Fiber"},
        }
    }
    sw_id = client.post("/api/devices", json=payload, headers=admin_headers).json()["id"]

    mock_interfaces = [
        {"if_index": 1, "name": "GE0/1", "status": "up", "speed_mbps": 1000},
        {"if_index": 2, "name": "GE0/2", "status": "down", "speed_mbps": 100},
        {"if_index": 3, "name": "GE0/3", "status": "down", "speed_mbps": 0},
    ]

    import app.services.snmp
    monkeypatch.setattr(app.services.snmp, "get_switch_interfaces", lambda **kwargs: mock_interfaces)

    resp = client.get(f"/api/devices/{sw_id}/snmp/interfaces", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["interfaces"]) == 3

    p1 = data["interfaces"][0]
    assert p1["if_index"] == 1
    assert p1["custom_description"] == "CoreRouter"
    assert p1["binding"]["target_name"] == "CoreRouter"

    p2 = data["interfaces"][1]
    assert p2["if_index"] == 2
    assert p2["custom_description"] == "ISP Fiber"

    p3 = data["interfaces"][2]
    assert p3["if_index"] == 3
    assert p3["custom_description"] == ""
    assert p3["binding"] is None
