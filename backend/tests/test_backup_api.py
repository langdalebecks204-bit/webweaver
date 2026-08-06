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


def test_import_replace_roundtrip(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "extra", "type": "switch", "ip_address": "10.0.0.99"})

    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=data)
    assert r.status_code == 200

    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"root", "grp", "sw1", "noip"}
    tree = client.get("/api/devices/tree", headers=admin_headers).json()
    assert tree[0]["name"] == "root"
    assert tree[0]["children"][0]["name"] == "grp"
    assert tree[0]["children"][0]["children"][0]["name"] == "sw1"
    assert client.get("/api/external", headers=admin_headers).json()[0]["name"] == "ext"


def test_import_merge_skips_existing_and_adds_new(client, admin_headers):
    _tree(client, admin_headers)
    backup = {
        "version": 1,
        "devices": [
            {"id": 1, "name": "root", "type": "group", "ip_address": None, "port": None,
             "order_index": 0, "parent_id": None},
            {"id": 2, "name": "grp", "type": "group", "ip_address": None, "port": None,
             "order_index": 0, "parent_id": 1},
            {"id": 3, "name": "swNEW", "type": "switch", "ip_address": "10.0.0.50",
             "port": None, "order_index": 0, "parent_id": 2},
        ],
        "external": [{"name": "ext", "ip_address": None, "domain": "example.com", "port": None}],
        "settings": [{"key": "poll_interval_minutes", "value": "3"}],
    }
    r = client.post("/api/backup/import?mode=merge", headers=admin_headers, json=backup)
    assert r.status_code == 200

    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"root", "grp", "sw1", "noip", "swNEW"}
    assert len(client.get("/api/external", headers=admin_headers).json()) == 1
    got = client.get("/api/settings/inspection-interval", headers=admin_headers).json()
    assert got["poll_interval_minutes"] == 3
    grp_children = [c["name"] for c in
                    client.get("/api/devices/tree", headers=admin_headers).json()[0]["children"][0]["children"]]
    assert "swNEW" in grp_children


def test_import_invalid_version(client, admin_headers):
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json={"version": 2})
    assert r.status_code == 422


def test_import_missing_device_name(client, admin_headers):
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                    json={"version": 1, "devices": [{"id": 1, "type": "group"}]})
    assert r.status_code == 422


def test_import_reschedules_interval(client, admin_headers, monkeypatch):
    from app.routers import backup as backup_router

    called = []
    monkeypatch.setattr(backup_router, "reschedule_interval", lambda m: called.append(m))
    data = {"version": 1, "settings": [{"key": "poll_interval_minutes", "value": "9"}]}
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=data)
    assert r.status_code == 200
    assert called and called[-1] == 9