中文 | [English](README.en.md)

# 织网 (WebWeaver)

树状结构自动化网络状态检测平台。后台定时/手动巡检设备（ICMP Ping + 可选 TCP 端口探测），前端以树形展示设备层级与实时状态，支持巡检历史记录与按小时/按天平均延时图表。

## 技术栈

- 后端：Python 3.12 / FastAPI / SQLAlchemy 2 / APScheduler / ping3 / PyJWT / bcrypt
- 前端：Vue 3 / Vite / Element Plus / Pinia / axios / ECharts
- 数据库：SQLite（单容器持久化到数据卷）

## 快速开始（本地开发）

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env              # Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

默认管理员：`admin` / `admin123`（请在 `.env` 中修改 `WEAVER_DEFAULT_ADMIN_PASSWORD`）。

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，用默认账号登录。

## Docker 部署

单容器多架构镜像（linux/amd64 + linux/arm64），发布到 GitHub Container Registry（`ghcr.io/langdalebecks204-bit/webweaver`）。首次部署：

```bash
docker run -d --name weaver \
  -p 8000:8000 \
  --cap-add=NET_RAW \
  -v webweaver-data:/data \
  -e WEAVER_JWT_SECRET=请改成随机长字符串 \
  ghcr.io/langdalebecks204-bit/webweaver:latest
```

- `--cap-add=NET_RAW`：ICMP Ping 必需（否则只能 TCP 探测）。
- `-v webweaver-data:/data`：SQLite 数据库持久化，重建容器不丢数据。
- 首次启动自动创建默认管理员 `admin` / `admin123`（生产务必通过 `WEAVER_DEFAULT_ADMIN_PASSWORD` 修改）。
- 前端静态资源已内置镜像中，浏览器访问 http://<主机>:8000 即可。

也可用 `docker compose up -d`（见仓库 `docker-compose.yml`，env 参考 `compose.env.example`）。

### 更新版本

```bash
# 固定 tag 方式（推荐）
docker pull ghcr.io/langdalebecks204-bit/webweaver:0.4.13
docker rm -f weaver
docker run -d --name weaver \
  -p 8000:8000 \
  --cap-add=NET_RAW \
  -v webweaver-data:/data \
  -e WEAVER_JWT_SECRET=请改成随机长字符串 \
  ghcr.io/langdalebecks204-bit/webweaver:0.4.13

# 或 compose 方式
docker compose pull
docker compose up -d
```

- 数据保存在卷 `webweaver-data:/data`，删除重建容器**不会丢数据**。
- 升级后启动时自动创建新表（如巡检历史表），旧数据无需手工迁移。
- 回滚：把镜像 tag 换回旧版本（如 `0.1.0`）重复上述步骤即可。

## 巡检说明

- 调度器默认每 5 分钟巡检一次（`WEAVER_POLL_INTERVAL_MINUTES`，可在前端设备页调整）。
- 状态判定：Ping 成功 → `online`；Ping 成功但 TCP 端口失败 → `warning`；Ping 失败 → `offline`；未巡检 → `unknown`。
- 每次巡检为带 IP 的节点写一条历史记录（状态 + 延时）。
- 树中右键节点可：添加子节点 / 添加同级 / 编辑 / 立即巡检 / **查看历史（带 IP 节点）** / 删除。
- 右键「查看历史」弹出平均延时柱状图：可切按小时/按天粒度、最近 1/7/30 天范围。
- 历史记录默认保留 30 天，自动清理（`WEAVER_PROBE_HISTORY_DAYS`，1-365）。
- 手机端设备树支持横向滚动查看深层嵌套。
- 设备支持上传图片（详情页右上角），自动压缩到最长边 1600px 且 ≤300KB。
- 上传接口拒绝超过 30MB 的文件；上传处理失败时保留原图。

### 内存要求

- 已在 **512MB 及以上内存** 的设备上验证：包括上传 48MP（约 8000x6000）手机照片并成功缩略。
- **512MB 以下内存未测试过图片上传**，请自行验证；大图上传主要内存消耗来自解码阶段，已在解码前预降采样以降低峰值内存。

## 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v

cd frontend
npm run test
```

## 环境变量（见 backend/.env.example）

| 变量 | 默认 | 说明 |
|---|---|---|
| WEAVER_DB_URL | sqlite:///./weaver.db | SQLAlchemy 连接串（容器内为 sqlite:////data/weaver.db） |
| WEAVER_JWT_SECRET | dev-secret-change-me | JWT 签名密钥（生产必改） |
| WEAVER_TOKEN_EXPIRE_MINUTES | 480 | token 有效期 |
| WEAVER_POLL_INTERVAL_MINUTES | 5 | 巡检周期（分钟） |
| WEAVER_PING_CONCURRENCY | 100 | 并发探测上限 |
| WEAVER_PING_TIMEOUT | 1.0 | ICMP 超时（秒） |
| WEAVER_TCP_TIMEOUT | 2.0 | TCP 探测超时（秒） |
| WEAVER_DEFAULT_ADMIN | admin | 首次启动的默认管理员 |
| WEAVER_DEFAULT_ADMIN_PASSWORD | admin123 | 默认管理员密码（生产必改） |
| WEAVER_ENABLE_SCHEDULER | true | 是否启用定时巡检 |
| WEAVER_PROBE_HISTORY_DAYS | 30 | 巡检历史保留天数（1-365） |
| WEAVER_FRONTEND_DIR | /app/frontend/dist | 前端静态资源目录（容器内默认即可） |

## 接口速览

- `POST /api/auth/login` 登录获取 JWT
- `GET /api/auth/me` 当前用户
- `GET /api/devices/tree` 设备树（嵌套 JSON）
- `GET|POST /api/devices` 列表 / 新建（admin）
- `PUT|DELETE /api/devices/{id}` 修改 / 删除（admin，级联删子树）
- `POST /api/devices/{id}/recheck` 立即巡检（含子树）
- `GET /api/devices/{id}/history?days=7` 巡检历史（登录即可）
- `GET /api/settings/inspection-interval` 巡检间隔（admin）
- `GET|PUT /api/settings/probe-history-days` 历史保留天数（admin）
- `GET|POST|PUT|DELETE /api/users` 用户管理（admin）
- `GET|POST /api/external` 外网目标（admin）
- `GET|PUT /api/backup` 备份与恢复（admin）

## 后续（Phase 3）

WebSocket 实时状态推送、MySQL 支持、掉包率统计。
