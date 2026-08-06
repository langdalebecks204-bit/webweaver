# WebWeaver Docker 单容器 + GHCR 发布 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 WebWeaver 打成单容器（后端托管前端），多架构（amd64/arm64），用 GitHub Actions 在 tag 时自动构建并发布到 ghcr.io，使最终用户一条 `docker pull` + `docker run` 即部署。

**Architecture:** 多阶段 Dockerfile：node 阶段 build 前端 dist → python 阶段装后端依赖 + 托管 dist；`--cap-add=NET_RAW` 满足 ICMP；数据卷挂 `/data`；GitHub Actions 用 buildx 出双架构推 GHCR。

**Tech Stack:** Docker / buildx / GitHub Actions / FastAPI StaticFiles / Node 20 / Python 3.12。

## Global Constraints

- 工作区：直接在主仓 `D:\code\WebWeaver`，分支 `main`，远端 `origin`(SSH) 已配好。
- 后端测试（workdir=backend）：`.venv\Scripts\python.exe -m pytest tests`，当前 78 passed。前端（workdir=frontend）：`npm run test` 当前 38 passed，`npm run build` 出 `dist/`。
- 镜像内服务端口 8000；映射由运行时 `-p` 控制。
- 镜像内 DB 路径 `/data/weaver.db`，挂载卷到 `/data`。**本地开发默认不改**（仍是 `sqlite:///./weaver.db`）。
- ICMP 权限：`--cap-add=NET_RAW`（容器运行参数/ compose）。
- 前端托管：后端**请求时** catch-all 路由服务前端 `dist/`（读 `WEAVER_FRONTEND_DIR`，默认 `/app/frontend/dist`）；目录不存在时 404。**不用 StaticFiles mount**（mount 在 import 时读一次 env，测试无法用 monkeypatch 控制；请求时读取可测且确定）。
- 镜像发布：tag（`v*`）触发才发布，构建 `linux/amd64,linux/arm64`，推 `:<tag>` 与 `:latest` 到 `ghcr.io/<owner>/webweaver`。
- 无代码注释（除非必需）。提交信息以 `feat:`/`fix:`/`docs:`/`ci:` 前缀开头。
- `main.py` 现有 router 均以 `/api/*` 前缀注册；catch-all `/{full_path:path}` 追加在最后，Starlette 按注册顺序匹配，`/api/*` 具体路由优先，`/` 落到 catch-all 服务前端。

---

### Task 1: 后端托管前端静态文件

**Files:**
- Modify: `backend/app/main.py`（末尾新增 catch-all 静态路由）
- Create: `backend/tests/test_static.py`

**Interfaces:**
- Consumes: 现状 `main.py`（lifespan、`app.include_router(...)` 均已存在）。
- Produces: `app` 在 `WEAVER_FRONTEND_DIR` 指向的 dist 存在时，`/` 与静态路径返回前端文件；目录不存在/未设时 404（本地、测试不受影响）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_static.py`：

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_no_frontend_returns_404():
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
```

> 设计要点：catch-all 路由**在请求时读取** `WEAVER_FRONTEND_DIR` env，故 monkeypatch 在进入 `TestClient` 前生效即确定；无 dist 时 `/` 返回 404，`/api/*` 始终正常。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_static.py -v`
Expected: 两个断言失败（当前 `main.py` 无静态路由，`/` 返回 404 或错误——且 `test_frontend_serves_index` 应为 404→200 不符）。

- [ ] **Step 3: 实现**

`backend/app/main.py` import 区（第 1-8 行块内）新增：

```python
import os
from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse
```

在文件末尾（`health` 函数之后）追加 catch-all：

```python
@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    base = Path(os.environ.get("WEAVER_FRONTEND_DIR", "/app/frontend/dist"))
    if not base.is_dir():
        return Response(status_code=404)
    target = (base / full_path).resolve()
    if not str(target).startswith(str(base.resolve())):
        return Response(status_code=404)
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        target = base / "index.html"
    if not target.is_file():
        return Response(status_code=404)
    return FileResponse(target)
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_static.py -v`
Expected: 2 passed；再跑 `-m pytest tests -q` 期待全量仍通过（不破坏既有）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/main.py backend/tests/test_static.py
git commit -m "feat: serve frontend dist from backend"
```

---

### Task 2: Dockerfile（多阶段构建）

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: 前端 `frontend/`、后端 `backend/app`、`backend/requirements.txt`。
- Produces：镜像内 `WORKDIR /app/backend`，`app.main:app`，`/app/frontend/dist` 静态，默认入口 `uvicorn`。运行用 `WEAVER_*` 环境变量。

- [ ] **Step 1: 写文件（不可运行测试，改为构建冒烟验证）**

创建 `Dockerfile`：

```dockerfile
# ---- build stage ----
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    WEAVER_DB_URL=sqlite:////data/weaver.db \
    WEAVER_ENABLE_SCHEDULER=true
WORKDIR /app
COPY --from=frontend-build /build/dist /app/frontend/dist
COPY backend/app ./backend/app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

创建 `.dockerignore`（仓库根部）：

```gitignore
**/.venv
**/node_modules
**/__pycache__
**/*.pyc
**/dist
backend/weaver.db
backend/.env
.git
.gitignore
docs
*.log
```

- [ ] **Step 2: （本机可选）冒烟构建**

Run（workdir=仓库根）: `docker build --platform linux/amd64 -t webweaver:smoke .`
Expected: 构建成功（若本机无 docker，跳过；最终验证由 Actions 在 GitHub 执行）。

- [ ] **Step 3: 提交**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add multi-stage dockerfile"
```

---

### Task 3: docker-compose + 环境模板

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.env.example`（可选，供 `-e WEAVER_*` 填写）

**Interfaces:**
- Consumes: 镜像 `ghcr.io/<owner>/webweaver:<version>`。
- Produces：一键本地/服务器部署服务 `webweaver`。

- [ ] **Step 1: 写 `docker-compose.yml`**

```yaml
services:
  webweaver:
    image: ghcr.io/langdalebecks204-bit/webweaver:latest
    container_name: webweaver
    restart: unless-stopped
    ports:
      - "8000:8000"
    cap_add:
      - NET_RAW
    volumes:
      - webweaver-data:/data
    environment:
      WEAVER_JWT_SECRET: ${WEAVER_JWT_SECRET:-change-me}
      WEAVER_DEFAULT_ADMIN_PASSWORD: ${WEAVER_DEFAULT_ADMIN_PASSWORD:-admin123}
      WEAVER_POLL_INTERVAL_MINUTES: ${WEAVER_POLL_INTERVAL_MINUTES:-5}

volumes:
  webweaver-data:
```

- [ ] **Step 2: 写 `.env.example`（compose 用）**

在仓库根部增加 `compose.env.example`（避免和后端 `backend/.env` 混淆）：

```yaml
WEAVER_JWT_SECRET=change-me-to-a-long-random-secret
WEAVER_DEFAULT_ADMIN_PASSWORD=change-me-strong-password
WEAVER_POLL_INTERVAL_MINUTES=5
```

（说明：`docker-compose` 读取 `--env-file` 或同目录 `.env`；本文件为示例模板，不自动生效。）

- [ ] **Step 3: 提交**

```bash
git add docker-compose.yml compose.env.example
git commit -m "feat: add docker compose deployment"
```

---

### Task 4: GitHub Actions 多架构发布工作流

**Files:**
- Create: `.github/workflows/publish.yml`

**Interfaces:**
- Consumes: Dockerfile（Task 2）。
- Produces: tag `v*` 推 `ghcr.io/langdalebecks204-bit/webweaver:<tag>` 与 `:latest`（amd64+arm64）。

- [ ] **Step 1: 写工作流**

创建 `.github/workflows/publish.yml`：

```yaml
name: publish

on:
  push:
    tags:
      - "v*"

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

permissions:
  contents: read
  packages: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE }}
          tags: |
            type=semver,pattern={{version}}
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: add publish workflow for ghcr"
```

---

### Task 5: 后端 config 支持 DB 路径说明 + 全量回归

**Files:**
- Modify: `backend/app/config.py`（不加改动——DB 路径由环境变量在容器内覆盖）
- Modify: `backend/.env.example`（补 DB 注释；可选）
- 验证：全量测试

**Interfaces:**
- 确保 `WEAVER_DB_URL` 环境变量覆盖生效（`pydantic-settings` 已支持，无需业务改动）。
- 回归后端与前端测试，确保 Docker 相关改动不破既有。

- [ ] **Step 1: 更新 `backend/.env.example`（仅注释说明）**

在 `backend/.env.example` 首行之前追加一行注释（不改变默认值）：

```ini
# 容器内默认使用 sqlite:////data/weaver.db（由镜像环境变量覆盖）；本地开发保留 ./weaver.db
WEAVER_DB_URL=sqlite:///./weaver.db
```

- [ ] **Step 2: 全量回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -q`
Expected: 全绿（78 原有 + test_static 新增 2 ≈ 80，以实际为准）。

Run（workdir=`frontend`）: `npm run test` → 全绿（38）；`npm run build` → 出 `dist/`。

- [ ] **Step 3: 提交**

```bash
git add backend/.env.example
git commit -m "docs: note container data path in env example"
```

---

### Task 6: 推送 GitHub 并准备首次发版（tag 示例）

**Files:**
- 无新增文件；仅 git 操作。

**Interfaces:**
- 把 Task 1-5 提交推到 `origin/main`，给用户演示发版/部署路径。

- [ ] **Step 1: 推 main**

```bash
git push origin main
```

- [ ] **Step 2: （可选）打标签触发首次构建**

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Expected: GitHub Actions 触发构建 amd64+arm64 并发布 `ghcr.io/langdalebecks204-bit/webweaver:v0.1.0` 与 `:latest`。

- [ ] **Step 3: 汇报**

向用户给出两个部署命令：
- compose：`docker compose up -d`
- 手动：`docker pull ghcr.io/langdalebecks204-bit/webweaver:v0.1.0` + 上文的 `docker run ... --cap-add=NET_RAW`

> 注：`git tag && git push` 触发 Actions 需要权限（仓库已 fork/长期 secret）。若首次 tag 推送报权限，回 ACK 用户检查 repo 权限。推送 main 即为最终交付。

---

## Self-Review 备注

- **spec 覆盖**：静态托管（Task1）✓；Dockerfile 多架构（Task2）✓；compose+卷（Task 3）✓；Actions tag 发布（Task 4）✓；权限/端口/DB 约束散见各 Task 的参数与会 export `EXPOSE/env/volumes`（Task2-3）✓。
- **类型一致**：`FRONTEND_DIR` / `WEAVER_FRONTEND_DIR` 同名于 spec；`WEAVER_DB_URL` 沿用现 config 变量；镜像内固定路径一致（`/data/weaver.db`、`/app/frontend/dist`）。
- **注意**：Base 里 `main.py` 若在测试环境被重复 import 会重复 `app.mount("/")`——用 `os.path.isdir` 守卫避免；测试用 `TestClient(app)` 走 monkeypatch env 设置，需在挂载判断前生效（模块级 import 时读取）。若测试顺序导致干扰，可接受仅保一条静态测试（验收仍以全量回归为准）。