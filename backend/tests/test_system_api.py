import pytest


def test_check_update_requires_admin(client):
    r = client.get("/api/system/update/check")
    assert r.status_code in (401, 403)


def test_apply_update_requires_admin(client):
    r = client.post(
        "/api/system/update/apply",
        json={"download_url": "http://example.com/update.tar.gz"},
    )
    assert r.status_code in (401, 403)


def test_check_update_admin(client, admin_headers, monkeypatch):
    async def mock_check(mirror=""):
        return {
            "current_version": "0.5.4",
            "latest_version": "0.5.5",
            "has_update": True,
            "release_notes": "test release",
            "published_at": "2026-09-20T00:00:00Z",
            "download_url": "http://test/update.tar.gz",
            "size": 1024,
        }

    monkeypatch.setattr("app.routers.system.check_github_update", mock_check)
    r = client.get("/api/system/update/check", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["has_update"] is True
    assert data["latest_version"] == "0.5.5"


def test_apply_update_admin_success(client, admin_headers, monkeypatch):
    def mock_apply(download_url, mirror="", skip_restart=True, allow_in_test=True):
        return {"status": "success", "message": "ok"}

    monkeypatch.setattr("app.routers.system.apply_update_package", mock_apply)
    r = client.post(
        "/api/system/update/apply",
        headers=admin_headers,
        json={"download_url": "http://test/update.tar.gz"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_apply_update_permission_error(client, admin_headers, monkeypatch):
    def mock_apply(download_url, mirror=""):
        raise PermissionError("not allowed in non-container")

    monkeypatch.setattr("app.routers.system.apply_update_package", mock_apply)
    r = client.post(
        "/api/system/update/apply",
        headers=admin_headers,
        json={"download_url": "http://test/update.tar.gz"},
    )
    assert r.status_code == 403
    assert "not allowed" in r.json()["detail"]
