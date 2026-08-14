import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _png_bytes(width=120, height=120, color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload_image(client, admin_headers, device_id, name="pic.png", content=_png_bytes()):
    return client.post(
        f"/api/devices/{device_id}/image",
        headers=admin_headers,
        files={"file": (name, content, "image/png")},
    )


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


def _export_json(client, headers):
    from app.services.backup_service import _parse_import_bytes

    r = client.get("/api/backup/export", headers=headers)
    assert r.status_code == 200
    data, _imgs = _parse_import_bytes(r.content)
    return data


def test_export_default_includes_all(client, admin_headers):
    _tree(client, admin_headers)
    data = _export_json(client, admin_headers)
    assert data["version"] == 2
    names = [d["name"] for d in data["devices"]]
    assert names[0] == "root"
    assert names[1] == "grp"
    assert set(names) == {"root", "grp", "sw1", "noip"}
    assert data["external"][0]["name"] == "ext"
    assert data["settings"] == [{"key": "poll_interval_minutes", "value": "7"}]


def test_export_subset(client, admin_headers):
    _tree(client, admin_headers)
    r = client.get("/api/backup/export", headers=admin_headers,
                   params={"include_external": "1"})
    data, _imgs = _parse_import_bytes(r.content)
    assert "devices" not in data
    assert "settings" not in data
    assert data["external"][0]["name"] == "ext"


def _parse_import_bytes(content):
    from app.services.backup_service import _parse_import_bytes

    return _parse_import_bytes(content)


def test_backup_export_admin_only(client):
    vh = _mk_viewer(client)
    assert client.get("/api/backup/export", headers=vh).status_code == 403


def test_import_replace_roundtrip(client, admin_headers):
    _tree(client, admin_headers)
    r = client.get("/api/backup/export", headers=admin_headers)
    content = r.content
    client.post("/api/devices", headers=admin_headers,
                json={"name": "extra", "type": "switch", "ip_address": "10.0.0.99"})

    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, content=content)
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
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                    data=json.dumps({"version": 3}))
    assert r.status_code == 422


def test_import_missing_device_name(client, admin_headers):
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                    data=json.dumps({"version": 1, "devices": [{"id": 1, "type": "group"}]}))
    assert r.status_code == 422


def test_import_reschedules_interval(client, admin_headers, monkeypatch):
    from app.routers import backup as backup_router

    called = []
    monkeypatch.setattr(backup_router, "reschedule_interval", lambda m: called.append(m))
    data = {"version": 1, "settings": [{"key": "poll_interval_minutes", "value": "9"}]}
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                    data=json.dumps(data))
    assert r.status_code == 200
    assert called and called[-1] == 9


def test_reset_clears_and_reseeds_admin(client, admin_headers):
    _tree(client, admin_headers)
    client.post("/api/users", headers=admin_headers,
                json={"username": "u1", "password": "pw123456", "role": "viewer"})

    r = client.post("/api/backup/reset", headers=admin_headers)
    assert r.status_code == 200

    assert client.get("/api/devices", headers=admin_headers).json() == []
    assert client.get("/api/external", headers=admin_headers).json() == []
    got = client.get("/api/settings/inspection-interval", headers=admin_headers).json()
    assert got["poll_interval_minutes"] == 5
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert me["username"] == "admin"
    assert client.post("/api/auth/login",
                       json={"username": "u1", "password": "pw123456"}).status_code == 401


def test_reset_reschedules_interval(client, admin_headers, monkeypatch):
    from app.config import settings as app_settings
    from app.routers import backup as backup_router

    called = []
    monkeypatch.setattr(backup_router, "reschedule_interval", lambda m: called.append(m))
    client.post("/api/backup/reset", headers=admin_headers)
    assert called and called[-1] == app_settings.poll_interval_minutes


def test_backup_import_and_reset_admin_only(client):
    vh = _mk_viewer(client)
    assert client.post("/api/backup/import?mode=replace", headers=vh,
                       json={"version": 1}).status_code == 403
    assert client.post("/api/backup/reset", headers=vh).status_code == 403


def test_export_returns_zip_with_weaver_json(client, admin_headers):
    _tree(client, admin_headers)
    r = client.get("/api/backup/export", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "weaver.json" in names
    data = json.loads(zf.read("weaver.json"))
    assert data["version"] == 2
    names_dev = [d["name"] for d in data["devices"]]
    assert set(names_dev) == {"root", "grp", "sw1", "noip"}


def test_export_zip_includes_device_images(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1"})
    cid = created.json()["id"]
    _upload_image(client, admin_headers, cid)

    r = client.get("/api/backup/export", headers=admin_headers)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    data = json.loads(zf.read("weaver.json"))
    dev = data["devices"][0]
    assert dev["image_file"] == f"images/{cid}.jpg"
    assert zf.read(f"images/{cid}.jpg")[:8] == b"\xff\xd8\xff\xe0" or zf.read(
        f"images/{cid}.jpg"
    )[:2] == b"\xff\xd8"


def test_import_zip_replace_roundtrip_with_image(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1"})
    cid = created.json()["id"]
    _upload_image(client, admin_headers, cid)
    got_before = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got_before["image_url"] is not None

    r = client.get("/api/backup/export", headers=admin_headers)
    content = r.content

    client.post("/api/devices", headers=admin_headers,
                json={"name": "extra", "type": "switch", "ip_address": "10.0.0.99"})
    resp = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                       content=content)
    assert resp.status_code == 200

    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"sw1"}
    restored = client.get("/api/devices", headers=admin_headers).json()[0]
    assert restored["image_url"] is not None
    assert _upload_path(restored["image_url"]).exists()


def test_import_legacy_json_still_works(client, admin_headers):
    data = {
        "version": 1,
        "devices": [{"id": 1, "name": "root", "type": "group"}],
    }
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=data)
    assert r.status_code == 200
    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"root"}


def test_import_backup_with_custom_type(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    payload = {
        "version": 2,
        "settings": [{"key": "custom_device_types", "value": '["nas2"]'}],
        "devices": [
            {
                "id": 1,
                "name": "NAS节点",
                "type": "nas2",
                "parent_id": None,
                "order_index": 0,
            }
        ],
    }
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=payload)
    assert r.status_code == 200
    devs = client.get("/api/devices", headers=admin_headers).json()
    assert any(d["name"] == "NAS节点" and d["type"] == "nas2" for d in devs)


def test_import_backup_with_custom_type_in_settings(client, admin_headers):
    payload = {
        "version": 2,
        "settings": [{"key": "custom_device_types", "value": '["nas2"]'}],
        "devices": [
            {
                "id": 1,
                "name": "NAS节点",
                "type": "nas2",
                "parent_id": None,
                "order_index": 0,
            }
        ],
    }
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=payload)
    assert r.status_code == 200
    devs = client.get("/api/devices", headers=admin_headers).json()
    assert any(d["name"] == "NAS节点" and d["type"] == "nas2" for d in devs)


def test_reset_clears_uploads(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "sw1", "type": "switch"})
    cid = created.json()["id"]
    _upload_image(client, admin_headers, cid)
    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert _upload_path(got["image_url"]).exists()

    client.post("/api/backup/reset", headers=admin_headers)
    assert not _upload_path(got["image_url"]).exists()


def _upload_path(image_url: str):
    from app.config import settings

    return Path(settings.upload_dir) / Path(image_url).name