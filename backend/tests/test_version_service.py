import json
from pathlib import Path
from app.services.version_service import get_current_version, is_container_env, is_update_allowed


def test_get_current_version_fallback():
    v = get_current_version()
    assert isinstance(v, str)
    assert len(v.split(".")) >= 3


def test_get_current_version_from_file(tmp_path, monkeypatch):
    version_file = tmp_path / "version.json"
    version_file.write_text(json.dumps({"version": "0.9.9"}), encoding="utf-8")
    monkeypatch.setattr("app.services.version_service.VERSION_FILE_PATH", version_file)
    assert get_current_version() == "0.9.9"


def test_is_container_env(monkeypatch):
    monkeypatch.setattr("app.services.version_service._check_dockerenv", lambda: True)
    assert is_container_env() is True


def test_is_update_allowed(monkeypatch):
    monkeypatch.setenv("WEAVER_ALLOW_INPLACE_UPDATE", "true")
    assert is_update_allowed() is True
    monkeypatch.delenv("WEAVER_ALLOW_INPLACE_UPDATE", raising=False)
    monkeypatch.setattr("app.services.version_service.is_container_env", lambda: False)
    assert is_update_allowed() is False
    monkeypatch.setattr("app.services.version_service.is_container_env", lambda: True)
    assert is_update_allowed() is True
