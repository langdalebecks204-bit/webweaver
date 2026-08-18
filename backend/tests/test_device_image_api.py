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


def test_upload_oversized_file_rejected(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    from app.services.image_service import MAX_UPLOAD_BYTES

    big = bytearray(MAX_UPLOAD_BYTES + 1024)
    big[0] = 0x89
    big[1] = 0x50
    big[2] = 0x4E
    big[3] = 0x47
    r = _upload(client, cid, admin_headers, bytes(big))
    assert r.status_code == 413


def test_process_uses_draft_before_load_for_large_jpeg(monkeypatch):
    import io as _io

    from PIL import Image

    from app.services.image_service import _process_image

    big = Image.new("RGB", (4000, 3000), (10, 20, 30))
    buf = _io.BytesIO()
    big.save(buf, format="JPEG", quality=90)
    raw = buf.getvalue()

    drafts = []

    orig_open = Image.open

    def fake_open(fp, *a, **kw):
        img = orig_open(fp, *a, **kw)
        orig_draft = img.draft

        def wrapped_draft(mode, size):
            drafts.append(size)
            return orig_draft(mode, size)

        img.draft = wrapped_draft
        return img

    monkeypatch.setattr(Image, "open", staticmethod(fake_open))
    out = _process_image(raw)
    assert out[:2] == b"\xff\xd8"
    target = next((s for s in drafts if s[0] > 1000 and s[1] > 1000), None)
    assert target is not None, "expected explicit draft() with large target size"
    assert max(target) <= 1600


def test_replace_image_keeps_old_file_on_processing_failure(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    uploaded = _upload(client, cid, admin_headers, _make_png()).json()
    old_path = _upload_path(uploaded["image_url"])
    assert os.path.exists(old_path)

    r = _upload(client, cid, admin_headers, b"corrupt-bytes", filename="pic.png",
                content_type="image/png")
    assert r.status_code == 422
    assert os.path.exists(old_path), "旧图片不应因新上传失败而丢失"
    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got["image_url"] == uploaded["image_url"]


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


def _make_jpeg_with_orientation(width=4032, height=3024, orientation=6) -> bytes:
    from PIL.ExifTags import Base as ExifTags

    img = Image.new("RGB", (width, height), (40, 90, 160))
    exif = Image.Exif()
    exif[ExifTags.Orientation] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, exif=exif)
    return buf.getvalue()


def test_strip_exif_removes_exif_and_returns_orientation(client, admin_headers):
    from app.services.image_service import strip_exif

    raw = _make_jpeg_with_orientation()
    clean, orientation = strip_exif(raw)
    assert clean is not None
    assert orientation == 6
    assert b"Exif\x00\x00" not in clean
    opened = Image.open(io.BytesIO(clean))
    assert opened.getexif().get(0x0112) is None


def test_strip_exif_returns_none_for_image_without_exif(client, admin_headers):
    from app.services.image_service import strip_exif

    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (1, 2, 3)).save(buf, format="PNG")
    clean, orientation = strip_exif(buf.getvalue())
    assert clean is None
    assert orientation is None


def test_process_image_safe_reembeds_orientation(client, admin_headers):
    from app.services.image_service import strip_exif, _process_image_safe

    raw = _make_jpeg_with_orientation()
    clean, orientation = strip_exif(raw)
    out = _process_image_safe(clean, orientation)
    assert out[:2] == b"\xff\xd8"
    saved = Image.open(io.BytesIO(out))
    assert saved.getexif().get(0x0112) == 6


def test_upload_exif_jpeg_succeeds_and_keeps_orientation(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch"})
    cid = created.json()["id"]
    raw = _make_jpeg_with_orientation()
    r = _upload(client, cid, admin_headers, raw, filename="phone.jpg", content_type="image/jpeg")
    assert r.status_code == 200
    path = _upload_path(r.json()["image_url"])
    assert os.path.exists(path)
    saved = Image.open(path)
    assert saved.getexif().get(0x0112) == 6
    assert os.path.getsize(path) <= 300 * 1024