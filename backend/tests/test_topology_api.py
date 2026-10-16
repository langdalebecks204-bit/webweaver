from unittest.mock import patch
from app.database import SessionLocal
from app.models import Device


def test_get_lldp_neighbors_unauthorized(client):
    r = client.get("/api/topology/lldp-neighbors")
    assert r.status_code == 401


def test_get_lldp_neighbors_mocked(client, admin_headers):
    with patch("app.routers.topology.discover_all_lldp_topology") as mock_disc:
        mock_disc.return_value = {
            "links": [
                {
                    "source_id": 1,
                    "source_name": "CoreSW",
                    "source_port": "GE0/1",
                    "target_id": 2,
                    "target_name": "Floor2SW",
                    "target_port": "GE0/24",
                    "is_bidirectional": True,
                }
            ],
            "unmatched_neighbors": [],
            "scanned_devices_count": 2,
        }
        r = client.get("/api/topology/lldp-neighbors", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data["links"]) == 1
        assert data["links"][0]["source_name"] == "CoreSW"
        assert data["links"][0]["target_name"] == "Floor2SW"


def test_apply_lldp_endpoint(client, admin_headers):
    with SessionLocal() as db:
        sw1 = Device(name="SW_Core", type="switch", port_count=24)
        sw2 = Device(name="SW_Leaf", type="switch", port_count=24)
        db.add_all([sw1, sw2])
        db.commit()
        id1, id2 = sw1.id, sw2.id

    payload = {
        "links": [
            {
                "source_id": id1,
                "target_id": id2,
                "source_port": "GE0/1",
                "target_port": "GE0/24",
            }
        ],
        "update_hierarchy": True,
    }
    r = client.post("/api/topology/apply-lldp", headers=admin_headers, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["applied_count"] == 2
