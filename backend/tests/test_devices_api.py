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


def test_list_serializes_last_check_with_utc_offset(client, admin_headers):
    from datetime import datetime, timezone
    from sqlalchemy import update

    from app.database import SessionLocal
    from app.models import Device

    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "TZ", "type": "switch", "ip_address": "1.1.1.1"})
    cid = created.json()["id"]
    with SessionLocal() as db:
        db.execute(update(Device).where(Device.id == cid)
                   .values(last_check=datetime(2026, 8, 14, 2, 30, 0)))
        db.commit()

    row = next(x for x in client.get("/api/devices", headers=admin_headers).json()
               if x["id"] == cid)
    assert row["last_check"] == "2026-08-14T02:30:00+00:00"

    detail = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert detail["last_check"] == "2026-08-14T02:30:00+00:00"


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

    async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size):
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


def test_recheck_all_devices(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size):
        return ProbeResult(status="online", latency_ms=5)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"}).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw2", "type": "switch", "ip_address": "10.0.0.2", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "noip", "type": "switch", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "grp", "type": "group", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "grpip", "type": "group", "ip_address": "10.0.0.9", "parent_id": root["id"]})

    r = client.post("/api/devices/recheck-all", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["checked"]) == 3
    assert all(c["status"] == "online" for c in body["checked"])
    assert body["external_checked"] == []


def test_recheck_all_viewer_allowed(client):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    r = client.post("/api/devices/recheck-all", headers=vh)
    assert r.status_code == 200
    assert r.json() == {"checked": [], "external_checked": []}


def test_recheck_all_requires_auth(client):
    assert client.post("/api/devices/recheck-all").status_code == 401


def test_recheck_all_includes_external(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size):
        return ProbeResult(status="online", latency_ms=6)

    async def fake_resolve(domain):
        return "8.8.8.8"

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    monkeypatch.setattr("app.inspector.engine.resolve_domain", fake_resolve)

    client.post("/api/external", headers=admin_headers,
                json={"name": "ext", "domain": "example.com"})

    r = client.post("/api/devices/recheck-all", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] == []
    assert len(body["external_checked"]) == 1
    assert body["external_checked"][0]["domain_status"] == "online"


def test_recheck_group_with_ip(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size):
        return ProbeResult(status="online", latency_ms=3)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "g", "type": "group", "ip_address": "10.0.0.9"},
    ).json()
    r = client.post(f"/api/devices/{created['id']}/recheck", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["checked"][0]["status"] == "online"


def test_create_switch_with_ports(client, admin_headers):
    r = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "unmanaged_switch", "port_count": 8,
              "uplink_port": 1,
              "port_bindings": {"1": {"target_id": 99, "type": "uplink"}}},
    )
    assert r.status_code == 409  # target 99 不存在


def test_create_unmanaged_switch_serializes_ports(client, admin_headers):
    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "unmanaged_switch", "port_count": 8, "uplink_port": 1},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["port_count"] == 8
    assert body["uplink_port"] == 1
    assert body["port_bindings"] is None

    got = client.get(f"/api/devices/{body['id']}", headers=admin_headers)
    assert got.json()["port_count"] == 8
    assert got.json()["uplink_port"] == 1


def test_switch_port_bindings_roundtrip(client, admin_headers):
    target = client.post("/api/devices", headers=admin_headers,
                         json={"name": "T", "type": "terminal", "ip_address": "1.1.1.1"}).json()
    sw = client.post("/api/devices", headers=admin_headers,
                     json={"name": "SW", "type": "switch", "port_count": 8,
                           "port_bindings": {"2": {"target_id": target["id"], "type": "downlink"}}})
    assert sw.status_code == 201
    body = sw.json()
    assert body["port_bindings"]["2"]["target_id"] == target["id"]

    upd = client.put(f"/api/devices/{body['id']}", headers=admin_headers,
                     json={"port_bindings": {"3": {"target_id": target["id"], "type": "downlink"}}})
    assert upd.status_code == 200
    assert upd.json()["port_bindings"]["3"]["target_id"] == target["id"]


def test_switch_port_out_of_range(client, admin_headers):
    r = client.post("/api/devices", headers=admin_headers,
                    json={"name": "SW", "type": "switch", "port_count": 4,
                          "port_bindings": {"5": {"target_id": 1, "type": "downlink"}}})
    assert r.status_code == 409


def test_non_switch_drops_port_fields(client, admin_headers):
    r = client.post("/api/devices", headers=admin_headers,
                    json={"name": "TERM", "type": "terminal", "port_count": 8, "uplink_port": 1})
    assert r.status_code == 201
    assert r.json()["port_count"] is None
    assert r.json()["uplink_port"] is None