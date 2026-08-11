import io
import os

from PIL import Image

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


def _make_png(width=200, height=200, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, device_id, headers, content, filename="pic.png", content_type="image/png"):
    return client.post(
        f"/api/devices/{device_id}/image",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


def test_upload_image_sets_image_url(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch", "ip_address": "1.1.1.1"})
    cid = created.json()["id"]

    r = _upload(client, cid, admin_headers, _make_png())
    assert r.status_code == 200
    body = r.json()
    assert "image_url" in body
    assert body["image_url"].startswith("/uploads/")

    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got["image_url"] == body["image_url"]
    assert os.path.exists(_upload_path(body["image_url"]))


def test_upload_rejects_unsupported_type(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    r = _upload(client, cid, admin_headers, b"not-an-image", filename="x.txt",
                content_type="text/plain")
    assert r.status_code == 422


def test_upload_rejects_bad_image_data(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    r = _upload(client, cid, admin_headers, b"garbage-data", filename="pic.png",
                content_type="image/png")
    assert r.status_code == 422


def test_upload_png_compressed_to_jpeg_under_limit(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    r = _upload(client, cid, admin_headers, _make_png(1600, 1600))
    assert r.status_code == 200
    path = _upload_path(r.json()["image_url"])
    assert os.path.getsize(path) <= 300 * 1024


def test_upload_requires_admin(client, admin_headers):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    assert _upload(client, cid, vh, _make_png()).status_code == 403


def test_delete_image_clears_url_and_file(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    uploaded = _upload(client, cid, admin_headers, _make_png()).json()
    path = _upload_path(uploaded["image_url"])
    assert os.path.exists(path)

    r = client.delete(f"/api/devices/{cid}/image", headers=admin_headers)
    assert r.status_code == 200
    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got["image_url"] is None
    assert not os.path.exists(path)


def test_delete_image_requires_admin(client, admin_headers):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    assert client.delete(f"/api/devices/{cid}/image", headers=vh).status_code == 403


def _upload_path(image_url: str) -> str:
    from app.config import settings

    return os.path.join(settings.upload_dir, os.path.basename(image_url))