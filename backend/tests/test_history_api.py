from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ProbeRecord, User
from app.security import hash_password


def _seed(device_id, checked_at, status="online", latency_ms=8):
    with SessionLocal() as db:
        db.add(ProbeRecord(device_id=device_id, checked_at=checked_at, status=status, latency_ms=latency_ms))
        db.commit()


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="histviewer", password_hash=hash_password("vp"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "histviewer", "password": "vp"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_history_returns_descending_records(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    assert dev.status_code == 201
    dev_id = dev.json()["id"]
    old = _now() - timedelta(hours=2)
    _seed(dev_id, old)
    _seed(dev_id, _now(), status="offline", latency_ms=None)

    r = client.get(f"/api/devices/{dev_id}/history", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["device_id"] == dev_id
    assert [rec["status"] for rec in body["records"]] == ["offline", "online"]
    assert body["records"][0]["latency_ms"] is None
    assert body["records"][1]["latency_ms"] == 8
    assert body["records"][0]["checked_at"] >= body["records"][1]["checked_at"]


def test_history_days_filters_old(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    _seed(dev_id, _now() - timedelta(days=10))
    _seed(dev_id, _now())

    r = client.get(f"/api/devices/{dev_id}/history?days=1", headers=admin_headers)
    assert len(r.json()["records"]) == 1


def test_history_not_found(client, admin_headers):
    assert client.get("/api/devices/99999/history", headers=admin_headers).status_code == 404


def test_history_viewer_can_read(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    _seed(dev_id, _now())
    vh = _mk_viewer(client)
    assert client.get(f"/api/devices/{dev_id}/history", headers=vh).status_code == 200


def test_history_empty_records(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    r = client.get(f"/api/devices/{dev_id}/history", headers=admin_headers)
    assert r.json() == {"device_id": dev_id, "records": []}
