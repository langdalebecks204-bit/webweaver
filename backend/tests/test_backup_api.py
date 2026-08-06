from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _tree(client, admin_headers):
    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"}).json()
    g = client.post("/api/devices", headers=admin_headers,
                    json={"name": "grp", "type": "group", "parent_id": root["id"]}).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1", "parent_id": g["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "noip", "type": "switch", "parent_id": g["id"]})
    client.post("/api/external", headers=admin_headers,
                json={"name": "ext", "domain": "example.com"})
    client.put("/api/settings/inspection-interval", headers=admin_headers,
               json={"poll_interval_minutes": 7})


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="v", password_hash=hash_password("pw123456"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "v", "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_export_default_includes_all(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers).json()
    assert data["version"] == 1
    names = [d["name"] for d in data["devices"]]
    assert names[0] == "root"
    assert names[1] == "grp"
    assert set(names) == {"root", "grp", "sw1", "noip"}
    assert data["external"][0]["name"] == "ext"
    assert data["settings"] == [{"key": "poll_interval_minutes", "value": "7"}]


def test_export_subset(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers,
                      params={"include_external": "1"}).json()
    assert "devices" not in data
    assert "settings" not in data
    assert data["external"][0]["name"] == "ext"


def test_backup_export_admin_only(client):
    vh = _mk_viewer(client)
    assert client.get("/api/backup/export", headers=vh).status_code == 403