import io
import tarfile
import pytest
from pathlib import Path
from app.services.update_service import (
    compare_semver,
    verify_update_archive,
    apply_update_package,
    resolve_download_url,
    check_github_update,
)


def test_compare_semver():
    assert compare_semver("0.5.4", "0.5.5") < 0
    assert compare_semver("0.5.5", "0.5.4") > 0
    assert compare_semver("0.5.4", "0.5.4") == 0
    assert compare_semver("v0.5.4", "0.5.5") < 0
    assert compare_semver("0.5.4", "v0.5.5") < 0


def test_resolve_download_url():
    raw_url = "https://github.com/langdalebecks204-bit/webweaver/releases/download/v0.5.5/webweaver-update.tar.gz"
    assert resolve_download_url(raw_url, "") == raw_url
    assert resolve_download_url(raw_url, "https://ghproxy.net/") == "https://ghproxy.net/" + raw_url
    assert resolve_download_url(raw_url, "https://ghproxy.net") == "https://ghproxy.net/" + raw_url
    proxied_url = "https://ghproxy.net/" + raw_url
    assert resolve_download_url(proxied_url, "https://ghproxy.net/") == proxied_url
    assert resolve_download_url(proxied_url, "") == raw_url
    assert resolve_download_url(proxied_url, "https://gh-proxy.com/") == "https://gh-proxy.com/" + raw_url


def test_verify_update_archive_invalid(tmp_path):
    bad_tar = tmp_path / "bad.tar.gz"
    bad_tar.write_bytes(b"not a tar")
    assert verify_update_archive(bad_tar) is False


def test_verify_update_archive_valid(tmp_path):
    good_tar = tmp_path / "good.tar.gz"
    with tarfile.open(good_tar, "w:gz") as tar:
        for name in ["version.json", "frontend/dist/index.html", "backend/app/main.py"]:
            data = b"ok"
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
    assert verify_update_archive(good_tar) is True


@pytest.mark.asyncio
async def test_check_github_update_mock(monkeypatch):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "tag_name": "v0.5.5",
                "published_at": "2026-09-20T10:00:00Z",
                "body": "Fixes and improvements",
                "assets": [
                    {
                        "name": "webweaver-update.tar.gz",
                        "browser_download_url": "https://github.com/releases/download/v0.5.5/webweaver-update.tar.gz",
                        "size": 3145728,
                    }
                ],
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url, headers=None):
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
    monkeypatch.setattr("app.services.update_service.get_current_version", lambda: "0.5.4")

    res = await check_github_update(mirror="https://ghproxy.net/")
    assert res["current_version"] == "0.5.4"
    assert res["latest_version"] == "0.5.5"
    assert res["has_update"] is True
    assert "https://ghproxy.net/" in res["download_url"]
    assert res["size"] == 3145728


def test_apply_update_rollback_on_failure(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend" / "app"
    backend_dir.mkdir(parents=True)
    (backend_dir / "main.py").write_text("original", encoding="utf-8")

    frontend_dir = tmp_path / "frontend" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("original-html", encoding="utf-8")

    monkeypatch.setattr("app.services.update_service.TEMP_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.update_service.download_file",
        lambda url, dest: dest.write_bytes(b"corrupt-data"),
    )

    with pytest.raises(Exception):
        apply_update_package(
            download_url="http://test/fake.tar.gz",
            target_backend_dir=backend_dir,
            target_frontend_dir=frontend_dir,
            skip_restart=True,
            allow_in_test=True,
        )

    assert (backend_dir / "main.py").read_text(encoding="utf-8") == "original"
    assert (frontend_dir / "index.html").read_text(encoding="utf-8") == "original-html"


def test_apply_update_success(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend" / "app"
    backend_dir.mkdir(parents=True)
    (backend_dir / "main.py").write_text("v1-code", encoding="utf-8")

    frontend_dir = tmp_path / "frontend" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("v1-html", encoding="utf-8")

    good_tar = tmp_path / "valid_update.tar.gz"
    with tarfile.open(good_tar, "w:gz") as tar:
        files = {
            "version.json": b'{"version": "0.5.5"}',
            "frontend/dist/index.html": b"v2-html",
            "backend/app/main.py": b"v2-code",
        }
        for name, data in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

    monkeypatch.setattr("app.services.update_service.TEMP_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.update_service.download_file",
        lambda url, dest: dest.write_bytes(good_tar.read_bytes()),
    )
    monkeypatch.setattr("app.services.update_service.init_db", lambda: None)

    res = apply_update_package(
        download_url="http://test/valid_update.tar.gz",
        target_backend_dir=backend_dir,
        target_frontend_dir=frontend_dir,
        skip_restart=True,
        allow_in_test=True,
    )
    assert res["status"] == "success"
    assert (backend_dir / "main.py").read_text(encoding="utf-8") == "v2-code"
    assert (frontend_dir / "index.html").read_text(encoding="utf-8") == "v2-html"
