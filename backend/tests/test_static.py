import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_api_health_works_without_frontend():
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404


def test_frontend_serves_index(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>hello</html>", encoding="utf-8")
    monkeypatch.setenv("WEAVER_FRONTEND_DIR", str(dist))
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "<html>" in r.text