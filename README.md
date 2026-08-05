# 织网 (WebWeaver)

树状结构自动化网络状态检测平台。后台定时/手动巡检设备（ICMP Ping + 可选 TCP 端口探测），前端以树形展示设备层级与实时状态。

当前为 **Phase 1 验证版**：登录 → 设备树维护 → 手动/定时巡检 → 状态展示，本地 SQLite 运行。

## 技术栈

- 后端：Python 3.12 / FastAPI / SQLAlchemy 2 / APScheduler / ping3 / PyJWT / bcrypt
- 前端：Vue 3 / Vite / Element Plus / Pinia / axios
- 数据库：开发 SQLite（SQLAlchemy 可切 MySQL，Phase 2 提供 Compose 部署）

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

## 巡检说明

- 调度器默认每 5 分钟巡检一次（`WEAVER_POLL_INTERVAL_MINUTES`）。
- 状态判定：Ping 成功 → `online`；Ping 成功但 TCP 端口失败 → `warning`；Ping 失败 → `offline`；未巡检 → `unknown`。
- 树中右键节点可：添加子节点 / 添加同级 / 编辑 / 立即巡检 / 删除。

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
| WEAVER_DB_URL | sqlite:///./weaver.db | SQLAlchemy 连接串 |
| WEAVER_JWT_SECRET | dev-secret-change-me | JWT 签名密钥 |
| WEAVER_TOKEN_EXPIRE_MINUTES | 480 | token 有效期 |
| WEAVER_POLL_INTERVAL_MINUTES | 5 | 巡检周期（分钟） |
| WEAVER_PING_CONCURRENCY | 100 | 并发探测上限 |
| WEAVER_PING_TIMEOUT | 1.0 | ICMP 超时（秒） |
| WEAVER_TCP_TIMEOUT | 2.0 | TCP 探测超时（秒） |
| WEAVER_DEFAULT_ADMIN | admin | 首次启动的默认管理员 |
| WEAVER_DEFAULT_ADMIN_PASSWORD | admin123 | 默认管理员密码（生产必改） |
| WEAVER_ENABLE_SCHEDULER | true | 是否启用定时巡检 |

## 接口速览

- `POST /api/auth/login` 登录获取 JWT
- `GET /api/auth/me` 当前用户
- `GET /api/devices/tree` 设备树（嵌套 JSON）
- `GET|POST /api/devices` 列表 / 新建（admin）
- `PUT|DELETE /api/devices/{id}` 修改 / 删除（admin，级联删子树）
- `POST /api/devices/{id}/recheck` 立即巡检（含子树）
- `GET|POST|PUT|DELETE /api/users` 用户管理（admin）

## 后续（Phase 2）

WebSocket 实时状态推送、用户管理界面、Docker Compose + MySQL 部署、前端轮询兜底。
