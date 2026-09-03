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
