# WebWeaver Docker + GitHub 容器发布 设计文档

> 日期：2026-08-06 ｜ 目标环境：PVE LXC / iStoreOS (x86) / iStoreOS ARM (armbian)

## 目标

让 WebWeaver 以「**单容器、多架构（amd64/arm64）**」镜像分发给最终用户，用户通过一条 `docker pull` + `docker run` 即可在任意支持的环境部署。镜像托管到 GitHub Container Registry（`ghcr.io`），由 GitHub Actions 在打版本 tag 时自动构建发布。

## 决策记录

| 项 | 决策 |
|---|---|
| 容器形态 | **单容器**：后端 FastAPI 同时托管前端 `dist/`，单端口 8000 |
| 镜像发布 | **GitHub Actions + buildx**，tag 触发才发布 |
| 架构 | `linux/amd64` + `linux/arm64` |
| ICMP 权限 | `--cap-add=NET_RAW`（最小权限） |
| 数据持久化 | SQLite 固定路径 `/data/weaver.db`，Docker 卷挂载 `/data` |
| 前端托管 | 后端新增 StaticFiles 服务 `/`，`/api/*` 保持 API 路由 |
| 端口 | 8000（映射由 `-p` 控制） |
| 配置 | `WEAVER_*` 环境变量（沿用 `backend/.env.example`，仅新增 DB 路径） |

## 架构

```
┌──────────── Docker 容器 ─────────────┐
│  uvicorn :8000                       │
│    ├── /api/*  → FastAPI 路由         │
│    └── /       → StaticFiles(frontend/dist)  │
│  数据卷 /data/weaver.db (SQLite)     │
└──────────────────────────────────────┘
        ↕ --cap-add=NET_RAW（ICMP 所需）
```

## 文件清单

- `Dockerfile`：多阶段构建
  - 阶段一 `node:20-alpine`：`npm ci` + `npm run build`
  - 阶段二 `python:3.12-slim`：装 `requirements.txt`（不含 dev），拷入 `frontend/dist` 与后端代码，`WORKDIR /app/backend`，CMD `uvicorn app.main:app`
- `.dockerignore`：排除 `.venv`、`node_modules`、`dist`（构建在容器内进行）、测试、`weaver.db`、`.git`
- `docker-compose.yml`：一键本地/服务器部署（含 `cap_add: [NET_RAW]`、卷、环境变量）
- `.github/workflows/publish.yml`：`on: push: tags: 'v*'` → `docker/build-push-action` + `docker/setup-buildx-action`，`platforms: linux/amd64,linux/arm64`，推 `ghcr.io/<owner>/webweaver:<tag>` 与 `:latest`
- `backend/app/main.py`：增加 StaticFiles 托管前端；db_url 默认改为 `sqlite:////data/weaver.db`（镜像内），本地开发不受影响

## 后端托管前端细节

`main.py` 在 `app` 创建后挂载：

```python
import os
from fastapi.staticfiles import StaticFiles
FRONTEND_DIR = os.environ.get("WEAVER_FRONTEND_DIR", "/app/frontend/dist")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
```

- `FRONTEND_DIR` 可覆盖：本地开发（无 dist）时不挂载；镜像内默认路径存在即挂载。
- `html=True` 支持 SPA 回退到 `index.html`。

## 数据库路径

- 镜像内默认 `WEAVER_DB_URL=sqlite:////data/weaver.db`（绝对路径，确保卷挂载生效）。
- 本地开发默认仍是 `sqlite:///./weaver.db`，不受影响。
- `backend/.env.example` 增加该默认说明。

## 测试策略

- 新增测试：`test_main.py`（或后端已存在测试中）验证「无 dist 时不挂载静态、有 dist 时 `/` 返回 index」。用 `tmp_path` 创建临时 dist 目录。
- 后端全量回归保持通过。
- 前端 `npm run build` 产出 dist 验证（本地手动验证一次即可）。
- 多架构构建由 GitHub Actions 在 tag 时验证；本地可先 `docker build` 单架构冒烟。

## 发布流程（用户侧）

```bash
git tag v1.0.0 && git push origin v1.0.0
# Actions 构建推送 ghcr.io/<owner>/webweaver:v1.0.0 和 :latest
```

## 部署（用户侧）

```bash
docker pull ghcr.io/langdalebecks204-bit/webweaver:v1.0.0
docker run -d --name webweaver --restart unless-stopped \
  --cap-add=NET_RAW \
  -p 8000:8000 \
  -v webweaver-data:/data \
  -e WEAVER_JWT_SECRET=<自定义> \
  -e WEAVER_DEFAULT_ADMIN_PASSWORD=<自定义> \
  ghcr.io/langdalebecks204-bit/webweaver:v1.0.0
```

## 验收标准

1. `docker build` 成功，单容器内同时能访问前端页面与 `/api/*`。
2. `docker run --cap-add=NET_RAW` 后 ICMP 巡检正常（容器内 ping 不报 PermissionError）。
3. 数据写入 `/data/weaver.db`，容器删除重建后数据仍在。
4. 打 tag 后 Actions 构建出 amd64+arm64 双架构镜像，`docker pull` 在 x86 与 ARM 均可用。
5. 本地后端测试全量通过。
