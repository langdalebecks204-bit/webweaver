from app.database import SessionLocal
from app.models import Device
from app.services import device_types as dt


def _mk_viewer(client):
    from app.models import User
    from app.security import hash_password

    with SessionLocal() as db:
        db.add(User(username="viewer_types", password_hash=hash_password("pass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer_types", "password": "pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_device_types(client, admin_headers):
    r = client.get("/api/settings/device-types", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "camera" in body["builtin"]
    assert body["custom"] == []


def test_add_custom_type(client, admin_headers):
    r = client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    assert r.status_code == 201
    assert "nas2" in r.json()["custom"]
    with SessionLocal() as db:
        assert "nas2" in dt.get_custom_types(db)


def test_add_custom_type_duplicates_and_invalid(client, admin_headers):
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "switch"}
    ).status_code == 409
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "nas2"}
    ).status_code == 201
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "nas2"}
    ).status_code == 409
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "a b"}
    ).status_code == 422
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "x" * 21}
    ).status_code == 422
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": ""}
    ).status_code == 422


def test_delete_custom_type_reassigns_devices(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "NAS2节点", "type": "nas2", "ip_address": "10.1.1.1"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "nas2"

    r = client.delete("/api/settings/device-types/nas2", headers=admin_headers)
    assert r.status_code == 200
    with SessionLocal() as db:
        dev = db.query(Device).filter(Device.name == "NAS2节点").one()
        assert dev.type == "terminal"


def test_delete_builtin_rejected(client, admin_headers):
    r = client.delete("/api/settings/device-types/camera", headers=admin_headers)
    assert r.status_code in (400, 422)


def test_create_device_with_custom_type(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "NAS节点", "type": "nas2", "ip_address": "10.2.2.2"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "nas2"


def test_create_device_with_unknown_type_rejected(client, admin_headers):
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "未知类型节点", "type": "bogus"},
    )
    assert r.status_code in (409, 422)


def test_device_types_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.post(
        "/api/settings/device-types", headers=vh, json={"name": "nas2"}
    ).status_code == 403
    assert client.delete("/api/settings/device-types/nas2", headers=vh).status_code == 403
    # GET 允许任意登录用户
    assert client.get("/api/settings/device-types", headers=vh).status_code == 200