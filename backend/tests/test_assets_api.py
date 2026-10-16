from unittest.mock import patch
from app.database import SessionLocal
from app.models import Device


def test_get_assets_unauthorized(client):
    r = client.get("/api/assets")
    assert r.status_code == 401


def test_get_assets_mocked(client, admin_headers):
    # Setup some devices in DB
    with SessionLocal() as db:
        sw = Device(
            name="CoreSwitch",
            type="switch",
            ip_address="192.168.1.1",
            mac_address="00:00:0C:01:02:03",
            snmp_enabled=True,
        )
        pc = Device(
            name="AdminPC",
            type="server",
            ip_address="192.168.1.50",
            mac_address="48:2C:6A:11:22:33",
        )
        db.add_all([sw, pc])
        db.commit()

    mock_entries = [
        {
            "ip": "192.168.1.50",
            "mac": "48:2C:6A:11:22:33",
            "vendor": "Apple",
            "if_index": 1,
            "if_name": "GigabitEthernet0/1",
            "source": "snmp",
        },
        {
            "ip": "192.168.1.120",
            "mac": "44:19:B6:55:66:77",
            "vendor": "Hikvision",
            "if_index": 2,
            "if_name": "GigabitEthernet0/2",
            "source": "snmp",
        },
    ]

    with patch("app.routers.assets.get_consolidated_assets") as mock_get:
        mock_get.return_value = [
            {
                "ip": "192.168.1.120",
                "mac": "44:19:B6:55:66:77",
                "vendor": "Hikvision",
                "if_index": 2,
                "if_name": "GigabitEthernet0/2",
                "collector_device_id": 1,
                "collector_device_name": "CoreSwitch",
                "source": "snmp",
                "is_managed": False,
                "managed_device_id": None,
                "managed_device_name": None,
                "managed_device_type": None,
                "location": None,
            },
            {
                "ip": "192.168.1.50",
                "mac": "48:2C:6A:11:22:33",
                "vendor": "Apple",
                "if_index": 1,
                "if_name": "GigabitEthernet0/1",
                "collector_device_id": 1,
                "collector_device_name": "CoreSwitch",
                "source": "snmp",
                "is_managed": True,
                "managed_device_id": 2,
                "managed_device_name": "AdminPC",
                "managed_device_type": "server",
                "location": None,
            },
        ]
        r = client.get("/api/assets", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["is_managed"] is False
        assert data[0]["vendor"] == "Hikvision"
        assert data[1]["is_managed"] is True


def test_enroll_asset_endpoint(client, admin_headers):
    # Enroll a new device from assets table
    enroll_payload = {
        "name": "NorthEntranceCamera",
        "type": "camera",
        "ip_address": "192.168.1.120",
        "mac_address": "44:19:B6:55:66:77",
        "location": "North Gate",
    }
    r = client.post("/api/assets/enroll", headers=admin_headers, json=enroll_payload)
    assert r.status_code == 201
    created = r.json()
    assert created["name"] == "NorthEntranceCamera"
    assert created["mac_address"] == "44:19:B6:55:66:77"
    assert created["type"] == "camera"
    assert created["location"] == "North Gate"
