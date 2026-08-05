from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _mk_viewer(username="viewer1", password="viewpass"):
    with SessionLocal() as db:
        db.add(User(username=username, password_hash=hash_password(password), role="viewer"))
        db.commit()


def _login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_tree_empty(client, admin_headers):
    r = client.get("/api/devices/tree", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_root_and_child(client, admin_headers):
    root = client.post(
        "/api/devices", headers=admin_headers, json={"name": "总部", "type": "group"}
    )
    assert root.status_code == 201
    root_id = root.json()["id"]

    sw = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "核心交换机", "type": "switch", "parent_id": root_id,
              "ip_address": "10.0.0.1", "port": 443},
    )
    assert sw.status_code == 201
    assert sw.json()["status"] == "unknown"

    tree = client.get("/api/devices/tree", headers=admin_headers).json()
    assert tree[0]["children"][0]["name"] == "核心交换机"


def test_list_and_filter(client, admin_headers):
    client.post("/api/devices", headers=admin_headers,
                json={"name": "A", "type": "switch", "ip_address": "10.0.0.1"})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "B", "type": "group"})
    all_items = client.get("/api/devices", headers=admin_headers).json()
    assert len(all_items) == 2
    switches = client.get("/api/devices", headers=admin_headers,
                          params={"type": "switch"}).json()
    assert len(switches) == 1


def test_duplicate_name_conflict(client, admin_headers):
    client.post("/api/devices", headers=admin_headers, json={"name": "dup", "type": "group"})
    r = client.post("/api/devices", headers=admin_headers, json={"name": "dup", "type": "group"})
    assert r.status_code == 409


def test_get_and_update(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch", "ip_address": "1.1.1.1"})
    cid = created.json()["id"]
    r = client.put(f"/api/devices/{cid}", headers=admin_headers,
                   json={"ip_address": "2.2.2.2"})
    assert r.status_code == 200
    assert r.json()["ip_address"] == "2.2.2.2"

    got = client.get(f"/api/devices/{cid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "S1"


def test_get_404(client, admin_headers):
    r = client.get("/api/devices/9999", headers=admin_headers)
    assert r.status_code == 404


def test_delete_cascade(client, admin_headers):
    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"})
    rid = root.json()["id"]
    child = client.post("/api/devices", headers=admin_headers,
                        json={"name": "child", "type": "group", "parent_id": rid})
    cid = child.json()["id"]
    r = client.delete(f"/api/devices/{rid}", headers=admin_headers)
    assert r.status_code == 200
    assert set(r.json()["deleted"]) == {rid, cid}
    assert client.get("/api/devices/tree", headers=admin_headers).json() == []


def test_viewer_forbidden_from_write(client, admin_headers):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    assert client.get("/api/devices/tree", headers=vh).status_code == 200
    assert client.post("/api/devices", headers=vh,
                       json={"name": "x", "type": "group"}).status_code == 403
    assert client.delete("/api/devices/9999", headers=vh).status_code == 403


def test_recheck_single_device(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=7)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "switch", "ip_address": "10.0.0.1", "port": 22},
    )
    cid = created.json()["id"]
    r = client.post(f"/api/devices/{cid}/recheck", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["checked"][0]["status"] == "online"

    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got["status"] == "online"
    assert got["latency_ms"] == 7