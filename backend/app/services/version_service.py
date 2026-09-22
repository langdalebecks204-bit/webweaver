import json
import os
from pathlib import Path

VERSION_FILE_PATH = Path("/app/version.json")
FALLBACK_VERSION = "0.5.7"


def _check_dockerenv() -> bool:
    return Path("/.dockerenv").exists() or Path("/app/backend/app").is_dir()


def is_container_env() -> bool:
    return _check_dockerenv()


def is_update_allowed() -> bool:
    if os.environ.get("WEAVER_ALLOW_INPLACE_UPDATE", "").lower() in ("true", "1", "yes"):
        return True
    return is_container_env()


def get_current_version() -> str:
    if VERSION_FILE_PATH.is_file():
        try:
            data = json.loads(VERSION_FILE_PATH.read_text(encoding="utf-8"))
            if "version" in data:
                return str(data["version"]).lstrip("v")
        except Exception:
            pass
    try:
        from app.main import app

        return str(app.version).lstrip("v")
    except Exception:
        return FALLBACK_VERSION
