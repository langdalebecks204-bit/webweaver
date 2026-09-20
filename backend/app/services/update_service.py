import asyncio
import os
import shutil
import tarfile
import threading
from pathlib import Path
from typing import Optional
import httpx

from app.database import init_db
from app.services.version_service import get_current_version, is_update_allowed

GITHUB_REPO = "langdalebecks204-bit/webweaver"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TAR_ASSET_NAME = "webweaver-update.tar.gz"
TEMP_DIR = Path(os.environ.get("WEAVER_TEMP_DIR", "/tmp" if Path("/tmp").exists() else os.environ.get("TEMP", "./uploads")))


def compare_semver(v1: str, v2: str) -> int:
    def parse(v: str):
        v = v.lstrip("v").strip()
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return parts

    p1, p2 = parse(v1), parse(v2)
    max_l = max(len(p1), len(p2))
    p1 += [0] * (max_l - len(p1))
    p2 += [0] * (max_l - len(p2))
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def resolve_download_url(raw_url: str, mirror: str = "") -> str:
    mirror = (mirror or "").strip()
    if not mirror:
        return raw_url
    if not mirror.endswith("/"):
        mirror += "/"
    return f"{mirror}{raw_url}"


async def check_github_update(mirror: str = "") -> dict:
    current_ver = get_current_version()
    api_url = GITHUB_API_LATEST
    headers = {
        "User-Agent": "WebWeaver-AutoUpdate/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(api_url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"查询 GitHub Release 失败 (HTTP {resp.status_code})")
        data = resp.json()

    tag_name = data.get("tag_name", "").lstrip("v")
    published_at = data.get("published_at", "")
    release_notes = data.get("body", "")

    asset_url = ""
    asset_size = 0
    for a in data.get("assets", []):
        if a.get("name") == TAR_ASSET_NAME:
            asset_url = a.get("browser_download_url", "")
            asset_size = a.get("size", 0)
            break

    has_update = compare_semver(current_ver, tag_name) < 0 if tag_name else False
    download_url = resolve_download_url(asset_url, mirror) if asset_url else ""

    return {
        "current_version": current_ver,
        "latest_version": tag_name,
        "has_update": has_update,
        "release_notes": release_notes,
        "published_at": published_at,
        "download_url": download_url,
        "size": asset_size,
    }


def verify_update_archive(archive_path: Path) -> bool:
    if not archive_path.is_file():
        return False
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
            required = ["version.json", "frontend/dist/index.html", "backend/app/main.py"]
            for req in required:
                if not any(n.endswith(req) or n == req for n in names):
                    return False
        return True
    except Exception:
        return False


def download_file(url: str, dest_path: Path):
    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"下载更新包失败 (HTTP {resp.status_code})")
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)


def _trigger_delayed_restart(delay_sec: float = 1.0):
    def _do_exit():
        os._exit(0)

    try:
        loop = asyncio.get_running_loop()
        loop.call_later(delay_sec, _do_exit)
    except RuntimeError:
        t = threading.Timer(delay_sec, _do_exit)
        t.daemon = True
        t.start()


def apply_update_package(
    download_url: str,
    mirror: str = "",
    target_backend_dir: Optional[Path] = None,
    target_frontend_dir: Optional[Path] = None,
    skip_restart: bool = False,
    allow_in_test: bool = False,
) -> dict:
    if not allow_in_test and not is_update_allowed():
        raise PermissionError("当前非 Docker 容器环境，已禁止执行在线热更新以保护代码。")

    actual_url = resolve_download_url(download_url, mirror)
    tar_dest = TEMP_DIR / "webweaver_latest.tar.gz"
    extract_temp = TEMP_DIR / "webweaver_extracted"
    backup_dir = TEMP_DIR / "webweaver_backup"

    target_backend = target_backend_dir or Path("/app/backend/app")
    target_frontend = target_frontend_dir or Path(os.environ.get("WEAVER_FRONTEND_DIR", "/app/frontend/dist"))

    download_file(actual_url, tar_dest)

    if not verify_update_archive(tar_dest):
        if tar_dest.exists():
            tar_dest.unlink()
        raise ValueError("下载的更新包格式损坏或缺少关键核心文件，升级已终止。")

    # 1. 备份当前目录
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if target_backend.exists():
        shutil.copytree(target_backend, backup_dir / "backend_app")
    if target_frontend.exists():
        shutil.copytree(target_frontend, backup_dir / "frontend_dist")

    # 2. 解压与覆盖
    try:
        if extract_temp.exists():
            shutil.rmtree(extract_temp)
        extract_temp.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_dest, "r:gz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(extract_temp, filter="data")
            else:
                tar.extractall(extract_temp)

        extracted_dist = next(extract_temp.glob("**/frontend/dist"), None)
        extracted_app = next(extract_temp.glob("**/backend/app"), None)
        extracted_version = next(extract_temp.glob("**/version.json"), None)

        if not extracted_dist or not extracted_app:
            raise ValueError("解压产物中未找到 frontend/dist 或 backend/app 目录")

        # 覆盖前端 dist
        if target_frontend.exists():
            shutil.rmtree(target_frontend)
        target_frontend.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(extracted_dist, target_frontend)

        # 覆盖后端 app
        if target_backend.exists():
            shutil.rmtree(target_backend)
        target_backend.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(extracted_app, target_backend)

        # 覆盖 version.json
        if extracted_version and Path("/app").is_dir():
            shutil.copy2(extracted_version, Path("/app/version.json"))

        # 覆盖 requirements.txt
        extracted_reqs = next(extract_temp.glob("**/backend/requirements.txt"), None)
        target_reqs = Path("/app/backend/requirements.txt")
        if extracted_reqs and target_reqs.parent.is_dir():
            shutil.copy2(extracted_reqs, target_reqs)

        # 3. 执行数据库迁移平滑升级
        init_db()

    except Exception as e:
        # 回滚
        if (backup_dir / "backend_app").exists():
            if target_backend.exists():
                shutil.rmtree(target_backend)
            shutil.copytree(backup_dir / "backend_app", target_backend)
        if (backup_dir / "frontend_dist").exists():
            if target_frontend.exists():
                shutil.rmtree(target_frontend)
            shutil.copytree(backup_dir / "frontend_dist", target_frontend)
        raise RuntimeError(f"更新解压失败，系统已自动回滚原版本: {e}")
    finally:
        # 清理临时文件
        if tar_dest.exists():
            try:
                tar_dest.unlink()
            except Exception:
                pass
        if extract_temp.exists():
            try:
                shutil.rmtree(extract_temp)
            except Exception:
                pass

    # 4. 触发延时重启
    if not skip_restart:
        _trigger_delayed_restart(1.0)

    return {"status": "success", "message": "系统更新已应用成功，服务正在自动重启..."}
