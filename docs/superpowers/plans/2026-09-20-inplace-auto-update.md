# 系统应用内差量热更新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 WebWeaver 在 Docker 容器环境下的应用内一键差量热更新功能，从 GitHub Releases 下载编译产物极小包（3MB~5MB）并在容器内原地替换与自动重启恢复，免去重新拉取全量 Docker 镜像的开销与闪存损耗。

**Architecture:** 
1. GitHub Actions 在 Tag 推送时编译前端并打包 `frontend/dist`、`backend/app`、`backend/requirements.txt` 及 `version.json` 为 `webweaver-update.tar.gz`，挂载至 Release 资产。
2. 后端新增 `/api/system/update` 模块：支持检测新版本（支持直连与国内加速代理）、校验完整性、代码快照备份回滚、原地解压覆盖、数据库结构平滑迁移、延时安全退出主进程（由 Docker `restart: unless-stopped` 毫秒级重拉容器）。
3. 前端新增 `UpdatePanel.vue`：展示当前版本与环境状态、镜像加速选择、更新日志呈现、一键升级进度模态框及服务就绪轮询自动刷新。

**Tech Stack:** Python 3.12 / FastAPI / httpx / tarfile / Vue 3 / Element Plus / Pinia / Vitest / Pytest / GitHub Actions。

## Global Constraints

- 工作区：直接在主仓 `D:\code\WebWeaver`，分支 `main`。
- 后端测试：`backend` 目录下 `.venv\Scripts\python.exe -m pytest tests`。
- 前端测试与构建：`frontend` 目录下 `npm test` 与 `npm run build`。
- 权限控制：更新相关接口仅限 `admin` 角色用户访问（依赖 `get_current_admin`）。
- 容器路径标准：
  - 前端静态目录：读取环境变量 `WEAVER_FRONTEND_DIR`，默认 `/app/frontend/dist`。
  - 后端源码目录：`/app/backend/app`（工作目录为 `/app/backend`）。
- 开发者防护机制：若在本地开发环境且未设置 `WEAVER_ALLOW_INPLACE_UPDATE=true`，拒绝执行 `apply`，严防开发目录被意外覆盖。

---

### Task 1: GitHub Actions 产出更新包与发布 Release

**Files:**
- Modify: `.github/workflows/publish.yml`

**Interfaces:**
- Consumes: 触发条件 `tags: - "[0-9]*"` 或 `tags: - "v[0-9]*"`。
- Produces: 产出物 `webweaver-update.tar.gz` 并作为 Release Asset 发布到 GitHub Release。

- [ ] **Step 1: 在 publish.yml 中添加 Tag 匹配规则与 Release 打包步骤**

修改 `.github/workflows/publish.yml`：
1. 监听 tags 增加 `v[0-9]*`。
2. 权限增加 `contents: write`。
3. 新增步骤：设置 Node 20、编译前端、生成 `version.json`、打包 `webweaver-update.tar.gz`、创建 GitHub Release 并上传资产。

```yaml
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Build frontend dist
        run: |
          cd frontend
          npm ci
          npm run build

      - name: Create update tarball
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          echo "{\"version\": \"$VERSION\", \"tag\": \"$GITHUB_REF_NAME\", \"built_at\": \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\"}" > version.json
          tar -czf webweaver-update.tar.gz version.json frontend/dist backend/app backend/requirements.txt

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: webweaver-update.tar.gz
          generate_release_notes: true
```

- [ ] **Step 2: 验证 publish.yml 语法有效性**

检查 YAML 格式正确无缩进错误。

- [ ] **Step 3: 提交 publish.yml**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: add webweaver-update.tar.gz packaging and release step"
```

---

### Task 2: 后端版本元数据与环境检测服务

**Files:**
- Create: `backend/app/services/version_service.py`
- Create: `backend/tests/test_version_service.py`

**Interfaces:**
- Produces: 
  - `get_current_version() -> str`：优先读取 `version.json`，次选 FastAPI app version。
  - `is_container_env() -> bool`：检测是否在 Docker / 容器环境中（检测 `/.dockerenv` 或 `/app/backend/app`）。
  - `is_update_allowed() -> bool`：判断当前环境是否允许热更新（容器环境或 `WEAVER_ALLOW_INPLACE_UPDATE=true`）。

- [ ] **Step 1: 编写失败测试 `backend/tests/test_version_service.py`**

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

运行：`.venv\Scripts\python.exe -m pytest tests/test_version_service.py`
预期：FAIL（模块尚未创建）

- [ ] **Step 3: 实现 `backend/app/services/version_service.py`**

```python
import json
import os
from pathlib import Path

VERSION_FILE_PATH = Path("/app/version.json")
FALLBACK_VERSION = "0.5.4"


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
```

- [ ] **Step 4: 运行测试验证通过**

运行：`.venv\Scripts\python.exe -m pytest tests/test_version_service.py`
预期：PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/services/version_service.py backend/tests/test_version_service.py
git commit -m "feat: add version detection and container environment check service"
```

---

### Task 3: 后端热更新核心服务 (检测、校验、备份、覆盖、重启)

**Files:**
- Create: `backend/app/services/update_service.py`
- Create: `backend/tests/test_update_service.py`

**Interfaces:**
- Produces:
  - `check_github_update(mirror: str = "") -> dict`: 请求 GitHub API，比对版本并返回下载资产信息。
  - `verify_update_archive(archive_path: Path) -> bool`: 检查压缩包是否包含必要文件。
  - `apply_update_package(download_url: str, mirror: str = "", target_backend_dir: Path = None, target_frontend_dir: Path = None, skip_restart: bool = False) -> dict`: 执行全流程升级。

- [ ] **Step 1: 编写单元测试 `backend/tests/test_update_service.py`**

测试涵盖：
1. `check_github_update` 正常响应解析与代理 URL 转换。
2. 版本号 semver 比较（新版识别）。
3. 压缩包校验（合法包 vs 损坏/缺文件包）。
4. 备份与还原机制（模拟解压异常时恢复原样）。
5. 正常解压覆盖与数据库迁移触发。

```python
import io
import tarfile
import pytest
from pathlib import Path
from app.services.update_service import (
    compare_semver,
    verify_update_archive,
    apply_update_package,
    resolve_download_url,
)

def test_compare_semver():
    assert compare_semver("0.5.4", "0.5.5") < 0
    assert compare_semver("0.5.5", "0.5.4") > 0
    assert compare_semver("0.5.4", "0.5.4") == 0
    assert compare_semver("v0.5.4", "0.5.5") < 0

def test_resolve_download_url():
    raw_url = "https://github.com/langdalebecks204-bit/webweaver/releases/download/v0.5.5/webweaver-update.tar.gz"
    assert resolve_download_url(raw_url, "") == raw_url
    assert resolve_download_url(raw_url, "https://ghproxy.net/") == "https://ghproxy.net/" + raw_url

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

def test_apply_update_rollback_on_failure(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend" / "app"
    backend_dir.mkdir(parents=True)
    (backend_dir / "main.py").write_text("original", encoding="utf-8")
    
    frontend_dir = tmp_path / "frontend" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("original-html", encoding="utf-8")
    
    # 模拟一个损坏的包
    corrupt_tar = tmp_path / "corrupt.tar.gz"
    corrupt_tar.write_bytes(b"corrupt")
    
    monkeypatch.setattr("app.services.update_service.download_file", lambda url, dest: dest.write_bytes(b"bad"))
    
    with pytest.raises(Exception):
        apply_update_package(
            download_url="http://test/fake.tar.gz",
            target_backend_dir=backend_dir,
            target_frontend_dir=frontend_dir,
            skip_restart=True,
            allow_in_test=True,
        )
    
    # 验证原文件完好无损
    assert (backend_dir / "main.py").read_text(encoding="utf-8") == "original"
    assert (frontend_dir / "index.html").read_text(encoding="utf-8") == "original-html"
```

- [ ] **Step 2: 运行测试验证失败**

运行：`.venv\Scripts\python.exe -m pytest tests/test_update_service.py`
预期：FAIL

- [ ] **Step 3: 实现 `backend/app/services/update_service.py`**

包含 GitHub Releases 请求、镜像拼接、tar 完整性检查、安全备份、原子目录替换、数据库初始化与异步安全退出。

```python
import asyncio
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Optional
import httpx

from app.database import init_db
from app.services.version_service import get_current_version, is_update_allowed

GITHUB_REPO = "langdalebecks204-bit/webweaver"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TAR_ASSET_NAME = "webweaver-update.tar.gz"
TEMP_DIR = Path("/tmp") if Path("/tmp").exists() else Path(os.environ.get("TEMP", "./uploads"))


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
    # 若使用了镜像代理且支持代理 API
    headers = {"User-Agent": "WebWeaver-AutoUpdate/1.0", "Accept": "application/vnd.github.v3+json"}
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
    backup_dir.mkdir(parents=True)
    if target_backend.exists():
        shutil.copytree(target_backend, backup_dir / "backend_app")
    if target_frontend.exists():
        shutil.copytree(target_frontend, backup_dir / "frontend_dist")

    # 2. 解压与覆盖
    try:
        if extract_temp.exists():
            shutil.rmtree(extract_temp)
        extract_temp.mkdir(parents=True)

        with tarfile.open(tar_dest, "r:gz") as tar:
            tar.extractall(extract_temp)

        # 查找解压出的 dist 与 app 目录
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
            tar_dest.unlink()
        if extract_temp.exists():
            shutil.rmtree(extract_temp)

    # 4. 触发延时重启
    if not skip_restart:
        asyncio.get_event_loop().call_later(1.0, lambda: os._exit(0))

    return {"status": "success", "message": "系统更新已应用成功，服务正在自动重启..."}
```

- [ ] **Step 4: 运行测试验证通过**

运行：`.venv\Scripts\python.exe -m pytest tests/test_update_service.py`
预期：PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/services/update_service.py backend/tests/test_update_service.py
git commit -m "feat: add update service with verification, backup, rollback and restart"
```

---

### Task 4: 后端路由与 API 接入 (`/api/system/update`)

**Files:**
- Create: `backend/app/routers/system.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_system_api.py`

**Interfaces:**
- Consumes: `app.services.update_service`, `app.routers.auth.get_current_admin`
- Produces: 
  - `GET /api/system/update/check`
  - `POST /api/system/update/apply`

- [ ] **Step 1: 编写路由测试 `backend/tests/test_system_api.py`**

测试非管理员 403、管理员 200、检查更新与应用更新参数校验。

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_check_update_requires_admin(client):
    r = client.get("/api/system/update/check")
    assert r.status_code in (401, 403)

def test_apply_update_requires_admin(client):
    r = client.post("/api/system/update/apply", json={"download_url": "http://example.com/update.tar.gz"})
    assert r.status_code in (401, 403)

def test_check_update_admin(admin_client, monkeypatch):
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
    r = admin_client.get("/api/system/update/check")
    assert r.status_code == 200
    data = r.json()
    assert data["has_update"] is True
    assert data["latest_version"] == "0.5.5"

def test_apply_update_admin(admin_client, monkeypatch):
    def mock_apply(download_url, mirror="", skip_restart=True, allow_in_test=True):
        return {"status": "success", "message": "ok"}
    monkeypatch.setattr("app.routers.system.apply_update_package", mock_apply)
    r = admin_client.post("/api/system/update/apply", json={"download_url": "http://test/update.tar.gz"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
```

- [ ] **Step 2: 运行测试验证失败**

运行：`.venv\Scripts\python.exe -m pytest tests/test_system_api.py`
预期：FAIL

- [ ] **Step 3: 实现 `backend/app/routers/system.py` 并注册到 `main.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.models import User
from app.routers.auth import get_current_admin
from app.services.update_service import check_github_update, apply_update_package

router = APIRouter()


class ApplyUpdateRequest(BaseModel):
    download_url: str
    mirror: Optional[str] = ""


@router.get("/update/check")
async def check_update(
    mirror: Optional[str] = Query(default=""),
    admin: User = Depends(get_current_admin),
):
    try:
        return await check_github_update(mirror=mirror)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/update/apply")
def apply_update(
    req: ApplyUpdateRequest,
    admin: User = Depends(get_current_admin),
):
    try:
        return apply_update_package(download_url=req.download_url, mirror=req.mirror)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

在 `backend/app/main.py` 中引入 `from app.routers import system` 并挂载：
```python
app.include_router(system.router, prefix="/api/system", tags=["system"])
```

- [ ] **Step 4: 运行测试验证通过**

运行：`.venv\Scripts\python.exe -m pytest tests/test_system_api.py`
预期：PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/routers/system.py backend/app/main.py backend/tests/test_system_api.py
git commit -m "feat: add /api/system/update endpoints for check and apply"
```

---

### Task 5: 前端 API 模块与 Pinia Store

**Files:**
- Create: `frontend/src/api/system.js`
- Create: `frontend/src/stores/system.js`
- Create: `frontend/src/stores/__tests__/system.spec.js`

**Interfaces:**
- Produces:
  - `systemApi.checkUpdate(mirror)`
  - `systemApi.applyUpdate(downloadUrl, mirror)`
  - `systemApi.healthCheck()`
  - `useSystemStore()`：管理当前版本、最新版本、更新日志、加速镜像配置、检查状态、升级动作与平滑重连轮询。

- [ ] **Step 1: 编写 Store 单元测试 `frontend/src/stores/__tests__/system.spec.js`**

测试：检查更新、状态赋值、应用更新及重连健康检查。

```javascript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSystemStore } from '../system'
import * as systemApi from '../../api/system'

vi.mock('../../api/system')

describe('SystemStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('checkUpdate updates state correctly', async () => {
    systemApi.checkUpdate.mockResolvedValue({
      data: {
        current_version: '0.5.4',
        latest_version: '0.5.5',
        has_update: true,
        release_notes: 'new features',
        download_url: 'http://test/tar.gz',
        size: 2048,
      },
    })
    const store = useSystemStore()
    await store.check()
    expect(store.currentVersion).toBe('0.5.4')
    expect(store.latestVersion).toBe('0.5.5')
    expect(store.hasUpdate).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

运行：`npm test src/stores/__tests__/system.spec.js`
预期：FAIL

- [ ] **Step 3: 实现 `frontend/src/api/system.js` 与 `frontend/src/stores/system.js`**

`src/api/system.js`:
```javascript
import axios from 'axios'

export function checkUpdate(mirror = '') {
  return axios.get('/api/system/update/check', { params: { mirror } })
}

export function applyUpdate(downloadUrl, mirror = '') {
  return axios.post('/api/system/update/apply', { download_url: downloadUrl, mirror })
}

export function healthCheck() {
  return axios.get('/api/health', { timeout: 1500 })
}
```

`src/stores/system.js`:
```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { applyUpdate, checkUpdate, healthCheck } from '../api/system'

export const useSystemStore = defineStore('system', () => {
  const currentVersion = ref('')
  const latestVersion = ref('')
  const hasUpdate = ref(false)
  const releaseNotes = ref('')
  const publishedAt = ref('')
  const downloadUrl = ref('')
  const packageSize = ref(0)
  const checking = ref(false)
  const selectedMirror = ref('https://ghproxy.net/')
  const customMirror = ref('')

  async function check() {
    checking.value = true
    try {
      const mirror = selectedMirror.value === 'custom' ? customMirror.value : selectedMirror.value
      const res = await checkUpdate(mirror)
      const data = res.data
      currentVersion.value = data.current_version
      latestVersion.value = data.latest_version
      hasUpdate.value = data.has_update
      releaseNotes.value = data.release_notes
      publishedAt.value = data.published_at
      downloadUrl.value = data.download_url
      packageSize.value = data.size
      return data
    } finally {
      checking.value = false
    }
  }

  async function apply() {
    const mirror = selectedMirror.value === 'custom' ? customMirror.value : selectedMirror.value
    return await applyUpdate(downloadUrl.value, mirror)
  }

  async function waitForHealth(maxAttempts = 30, intervalMs = 1000) {
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, intervalMs))
      try {
        const res = await healthCheck()
        if (res.status === 200) {
          return true
        }
      } catch (e) {
        // service restarting, ignore
      }
    }
    throw new Error('等待服务重启超时，请手动刷新页面。')
  }

  return {
    currentVersion,
    latestVersion,
    hasUpdate,
    releaseNotes,
    publishedAt,
    downloadUrl,
    packageSize,
    checking,
    selectedMirror,
    customMirror,
    check,
    apply,
    waitForHealth,
  }
})
```

- [ ] **Step 4: 运行测试验证通过**

运行：`npm test src/stores/__tests__/system.spec.js`
预期：PASS

- [ ] **Step 5: 提交代码**

```bash
git add frontend/src/api/system.js frontend/src/stores/system.js frontend/src/stores/__tests__/system.spec.js
git commit -m "feat: add frontend system API client and pinia store"
```

---

### Task 6: 前端 UpdatePanel 组件与 MainView 标签页集成

**Files:**
- Create: `frontend/src/components/UpdatePanel.vue`
- Create: `frontend/src/components/__tests__/UpdatePanel.spec.js`
- Modify: `frontend/src/views/MainView.vue`

**Interfaces:**
- Consumes: `useSystemStore()`, `MainView.vue`
- Produces: 完整交互的系统更新卡片与升级进度弹窗，支持心跳等待与自动刷新页面。

- [ ] **Step 1: 编写组件测试 `frontend/src/components/__tests__/UpdatePanel.spec.js`**

测试卡片渲染、检查更新按钮、新版本信息展示与更新触发逻辑。

```javascript
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import UpdatePanel from '../UpdatePanel.vue'
import { useSystemStore } from '../../stores/system'

describe('UpdatePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders check button and version info', () => {
    const store = useSystemStore()
    store.currentVersion = '0.5.4'
    const wrapper = mount(UpdatePanel, {
      global: {
        stubs: {
          'el-card': { template: '<div><slot name="header"/><slot/></div>' },
          'el-tag': true,
          'el-select': true,
          'el-option': true,
          'el-button': true,
          'el-dialog': true,
          'el-progress': true,
        },
      },
    })
    expect(wrapper.text()).toContain('系统差量更新')
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

运行：`npm test src/components/__tests__/UpdatePanel.spec.js`
预期：FAIL

- [ ] **Step 3: 创建 `frontend/src/components/UpdatePanel.vue`**

实现卡片式 UI：
1. 当前系统版本与运行环境。
2. 镜像加速选择器（直连、ghproxy.net、gh-proxy.com、自定义）。
3. 检查更新按钮与加载状态。
4. 发现新版本卡片：展示版本号、文件大小、发布说明（Release Notes）。
5. 升级弹窗：展示步骤进度（下载校验 -> 部署覆盖 -> 重启中），自动轮询 `/api/health`，成功后提示并调用 `window.location.reload()`。

- [ ] **Step 4: 在 `frontend/src/views/MainView.vue` 中挂载【系统更新】标签页**

在 `MainView.vue` 中导入 `UpdatePanel.vue`，并在 `v-if="isAdmin"` 的标签组中追加：
```html
<el-tab-pane v-if="isAdmin" label="系统更新" name="update">
  <UpdatePanel />
</el-tab-pane>
```

- [ ] **Step 5: 运行前端全量测试验证**

运行：`npm test`
预期：所有前端测试全部 PASS。

- [ ] **Step 6: 提交前端代码**

```bash
git add frontend/src/components/UpdatePanel.vue frontend/src/components/__tests__/UpdatePanel.spec.js frontend/src/views/MainView.vue
git commit -m "feat: add UpdatePanel UI and mount system update tab in MainView"
```

---

### Task 7: 全系统测试验证与构建校验

**Files:**
- None (执行校验)

**Interfaces:**
- Consumes: 全量测试套件与生产打包命令。

- [ ] **Step 1: 运行全量后端测试**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests`
预期：所有测试通过（156+ passed）。

- [ ] **Step 2: 运行全量前端测试**

运行：`cd frontend && npm test`
预期：所有测试通过（130+ passed）。

- [ ] **Step 3: 运行前端生产编译构建**

运行：`cd frontend && npm run build`
预期：编译成功，生成 `frontend/dist` 无任何语法或构建报错。

- [ ] **Step 4: 提交并推送到远端 (若用户确认)**
