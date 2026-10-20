from unittest.mock import patch
from app.database import SessionLocal
from app.models import Device


def test_edge_discover_unauthorized(client):
    r = client.post("/api/topology/edge-discover")
    assert r.status_code == 401


def test_edge_discover_mocked(client, admin_headers):
    with patch("app.routers.topology.discover_edge_topology") as mock_disc:
        mock_disc.return_value = {
            "direct_terminals": [
                {
                    "switch_id": 1,
                    "switch_name": "CoreSW",
                    "port_num": 5,
                    "port_name": "GE5",
                    "device_id": 10,
                    "device_name": "PC-1",
                    "mac": "00:11:22:33:44:55",
                }
            ],
            "unmanaged_hubs": [],
            "ap_clusters": [],
        }
        r = client.post("/api/topology/edge-discover", headers=admin_headers, json={})
        assert r.status_code == 200
        data = r.json()
        assert len(data["direct_terminals"]) == 1
        assert data["direct_terminals"][0]["device_name"] == "PC-1"


def test_apply_edge_endpoint(client, admin_headers):
    with SessionLocal() as db:
        sw = Device(name="SW_Edge_Test", type="switch", port_count=24)
        c1 = Device(name="Client_1", type="server")
        c2 = Device(name="Client_2", type="server")
        db.add_all([sw, c1, c2])
        db.commit()
        sw_id, c1_id, c2_id = sw.id, c1.id, c2.id

    payload = {
        "direct_terminals": [
            {"device_id": c1_id, "switch_id": sw_id, "port_num": 1, "port_name": "GE1"}
        ],
        "hubs_to_create": [
            {
                "name": "会议室分线交换机",
                "switch_id": sw_id,
                "port_num": 8,
                "port_name": "GE8",
                "device_ids": [c2_id],
                "unregistered_macs": ["00:AA:BB:CC:DD:EE"],
            }
        ],
    }
    r = client.post("/api/topology/apply-edge", headers=admin_headers, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["applied_direct_count"] == 1
    assert data["created_hubs_count"] == 1

    with SessionLocal() as db:
        dev1 = db.get(Device, c1_id)
        assert dev1.parent_id == sw_id
        dev2 = db.get(Device, c2_id)
        hub = db.query(Device).filter_by(name="会议室分线交换机").first()
        assert hub is not None
        assert dev2.parent_id == hub.id
