from app.database import SessionLocal
from app.models import Setting, User
from app.security import hash_password


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="viewer1", password_hash=hash_password("viewpass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewpass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_interval_returns_default(client, admin_headers):
    r = client.get("/api/settings/inspection-interval", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"poll_interval_minutes": 5}


def test_put_interval_persists_and_returns(client, admin_headers):
    r = client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 30},
    )
    assert r.status_code == 200
    assert r.json() == {"poll_interval_minutes": 30}

    got = client.get("/api/settings/inspection-interval", headers=admin_headers)
    assert got.json() == {"poll_interval_minutes": 30}

    with SessionLocal() as db:
        row = db.get(Setting, "poll_interval_minutes")
        assert row is not None
        assert row.value == "30"


def test_put_interval_reschedules(client, admin_headers, monkeypatch):
    calls = []

    def fake_reschedule(minutes):
        calls.append(minutes)

    monkeypatch.setattr("app.routers.settings.reschedule_interval", fake_reschedule)
    r = client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 10},
    )
    assert r.status_code == 200
    assert calls == [10]


def test_interval_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/settings/inspection-interval", headers=vh).status_code == 403
    assert client.put(
        "/api/settings/inspection-interval",
        headers=vh,
        json={"poll_interval_minutes": 10},
    ).status_code == 403


def test_interval_out_of_range(client, admin_headers):
    assert client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 0},
    ).status_code == 422
    assert client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 1441},
    ).status_code == 422


def test_probe_history_days_default(client, admin_headers):
    r = client.get("/api/settings/probe-history-days", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"probe_history_days": 30}


def test_probe_history_days_put_persists(client, admin_headers):
    r = client.put(
        "/api/settings/probe-history-days",
        headers=admin_headers,
        json={"probe_history_days": 60},
    )
    assert r.status_code == 200
    assert r.json() == {"probe_history_days": 60}

    got = client.get("/api/settings/probe-history-days", headers=admin_headers)
    assert got.json() == {"probe_history_days": 60}

    with SessionLocal() as db:
        row = db.get(Setting, "probe_history_days")
        assert row.value == "60"


def test_probe_history_days_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/settings/probe-history-days", headers=vh).status_code == 403
    assert client.put(
        "/api/settings/probe-history-days", headers=vh, json={"probe_history_days": 10}
    ).status_code == 403


def test_probe_history_days_out_of_range(client, admin_headers):
    assert client.put(
        "/api/settings/probe-history-days", headers=admin_headers, json={"probe_history_days": 0}
    ).status_code == 422
    assert client.put(
        "/api/settings/probe-history-days", headers=admin_headers, json={"probe_history_days": 366}
    ).status_code == 422
