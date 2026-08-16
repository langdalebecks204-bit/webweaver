from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="viewer1", password_hash=hash_password("viewpass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewpass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_list_update_delete(client, admin_headers):
    r = client.post("/api/external", headers=admin_headers,
                    json={"name": "公网", "ip_address": "8.8.8.8", "domain": "example.com"})
    assert r.status_code == 201
    target_id = r.json()["id"]
    assert r.json()["ip_status"] == "unknown"

    lst = client.get("/api/external", headers=admin_headers).json()
    assert len(lst) == 1
    assert lst[0]["domain"] == "example.com"

    up = client.put(f"/api/external/{target_id}", headers=admin_headers,
                    json={"name": "改名"})
    assert up.status_code == 200
    assert up.json()["name"] == "改名"

    d = client.delete(f"/api/external/{target_id}", headers=admin_headers)
    assert d.status_code == 200
    assert client.get("/api/external", headers=admin_headers).json() == []


def test_create_requires_target(client, admin_headers):
    r = client.post("/api/external", headers=admin_headers, json={"name": "x"})
    assert r.status_code == 422


def test_update_missing_404(client, admin_headers):
    r = client.put("/api/external/9999", headers=admin_headers, json={"name": "x"})
    assert r.status_code == 404


def test_external_admin_only_write(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/external", headers=vh).status_code == 200
    assert client.post("/api/external", headers=vh,
                       json={"name": "x", "ip_address": "1.1.1.1"}).status_code == 403
    assert client.delete("/api/external/1", headers=vh).status_code == 403


def test_check_all_updates_results(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size):
        return ProbeResult(status="online", latency_ms=4)

    async def fake_resolve(domain):
        return "8.8.8.8"

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    monkeypatch.setattr("app.inspector.engine.resolve_domain", fake_resolve)

    client.post("/api/external", headers=admin_headers,
                json={"name": "a", "ip_address": "8.8.8.8"})
    client.post("/api/external", headers=admin_headers,
                json={"name": "b", "domain": "example.com"})

    r = client.post("/api/external/check-all", headers=admin_headers)
    assert r.status_code == 200
    checked = r.json()["checked"]
    assert len(checked) == 2
    assert all(c["ip_status"] == "online" or c["domain_status"] == "online" for c in checked)
    assert all(c["ip_last_check"] is not None or c["domain_last_check"] is not None for c in checked)


def test_check_all_requires_auth(client):
    assert client.post("/api/external/check-all").status_code == 401
