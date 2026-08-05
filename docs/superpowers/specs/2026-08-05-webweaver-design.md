# 织网 (WebWeaver) — 树状结构自动化网络状态检测平台 设计文档

日期：2026-08-05
状态：已批准（用户确认后进入实现规划）

## 1. 概述

织网（WebWeaver）是一个具有层级（树状）结构的自动化网络状态检测平台。后台定时巡检网络设备（Ping / TCP 端口探测），前端以树状结构展示设备层级与实时状态，并支持设备与用户的增删改查。

### 1.1 目标（v1 验证版）

- 提供一套可运行的最小闭环：登录 → 树状展示设备 → 定时巡检 → 状态实时刷新。
- 设备节点支持分组（group）与真实设备（server/switch/terminal），通过 `parent_id` 邻接表维持层级。
- 巡检引擎并发执行 ICMP Ping + 可选 TCP 端口探测，结果写回数据库并推送 WebSocket 事件。
- 支持多用户与角色（admin / viewer）。
- 本地开发用 SQLite，生产部署用 MySQL（经 SQLAlchemy 切换）。
- 可部署到 Linux 裸机或 Docker 容器。

### 1.2 已确认的决策

| 议题 | 决策 |
|---|---|
| 数据库 | SQLAlchemy ORM；开发 SQLite / 生产 MySQL，连接串由环境变量切换 |
| 前端 | Vue 3 + Element Plus（el-tree） |
| 检测方式 | ICMP Ping + 可选 TCP 端口探测（不含 SNMP） |
| 实时推送 | v1 包含 WebSocket，状态切换即时推送；前端带轮询兜底 |
| 认证 | 多用户 + 角色（admin / viewer）+ 用户管理界面 |
| 后端拓扑 | 单个 FastAPI 进程承载 REST API + APScheduler + WebSocket |

## 2. 仓库结构

```
WebWeaver/
├── backend/                 # Python 3.12，虚拟环境 venv
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI 应用 + lifespan（启动/停止调度器）
│   │   ├── config.py        # 环境变量配置（DB URL、JWT、巡检间隔等）
│   │   ├── database.py      # SQLAlchemy engine / SessionLocal / Base
│   │   ├── models.py        # Device、User（SQLAlchemy 模型）
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   ├── auth.py          # JWT、密码哈希、角色依赖
│   │   ├── deps.py          # get_db / get_current_user / require_admin
│   │   ├── routers/
│   │   │   ├── auth.py      # login、/me
│   │   │   ├── users.py     # 用户管理（admin）
│   │   │   └── devices.py   # 设备 CRUD、tree 接口、recheck
│   │   ├── inspector/
│   │   │   ├── engine.py    # 异步并发 Ping + TCP 探测
│   │   │   └── scheduler.py # APScheduler 任务注册
│   │   └── websockets.py    # WebSocket 连接管理器
│   ├── tests/               # pytest
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # Vite + Vue3 + Element Plus + Pinia + vue-router
│   ├── src/
│   │   ├── api/             # axios 封装
│   │   ├── stores/          # Pinia（auth / devices）
│   │   ├── components/      # DeviceTree、StatusDot、UserManage 等
│   │   ├── views/           # LoginView、MainView、UsersView
│   │   └── ws/              # WebSocket 客户端
│   ├── package.json
│   └── vite.config.js
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend  # 构建后由 nginx 托管 + 反向代理
│   └── nginx.conf
├── docker-compose.yml       # backend + frontend(nginx) + mysql
├── .env.example             # 根级 compose 环境变量
├── .gitignore
└── README.md                # 开发 / 部署说明
```

## 3. 数据模型

### 3.1 devices（邻接表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 节点唯一标识 |
| parent_id | INT NULL FK→devices.id | 父节点；NULL 表示根节点（不允许自引用/成环） |
| name | VARCHAR(100) | 节点名称（如"一楼机房"、"核心交换机"） |
| type | VARCHAR(20) | `group` \| `server` \| `switch` \| `terminal` |
| ip_address | VARCHAR(45) NULL | 设备 IP（IPv4/IPv6 空间）；`group` 类型为空 |
| port | INT NULL | 可选 TCP 探测端口（如 22/80/443） |
| status | VARCHAR(10) | `unknown` \| `online` \| `warning` \| `offline` |
| latency_ms | INT NULL | 最近一次 Ping 时延（毫秒） |
| last_check | DATETIME NULL | 最近一次巡检时间 |
| order_index | INT DEFAULT 0 | 同级排序 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

- 约束：同一 `parent_id` 下 `name` 唯一（软约束，应用层校验）；`parent_id` 不能指向自身。
- 删除节点时级联删除其整棵子树（前端需二次确认）。

### 3.2 users

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| username | VARCHAR(50) UNIQUE | 登录名 |
| password_hash | VARCHAR(255) | bcrypt 哈希 |
| role | VARCHAR(10) | `admin` \| `viewer` |
| created_at | DATETIME | |

### 3.3 状态定义

| 状态 | 判定 |
|---|---|
| unknown | 尚未巡检（或检测无法判定） |
| online | Ping 成功；若配置了 port，则 TCP 端口也连通 |
| warning | Ping 成功，但配置了 port 且 TCP 端口探测失败（或时延超阈值） |
| offline | Ping 超时 / 不可达 / ICMP 错误 |

## 4. 巡检引擎

- **调度**：APScheduler `BackgroundScheduler`，`interval` 触发，间隔 `WEAVER_POLL_INTERVAL_MINUTES`（默认 5 分钟），`coalesce=True, max_instances=1` 防止任务重叠。
- **执行**：每次任务开启一个 asyncio 事件循环（在运行中的 FastAPI 进程内），读取所有 `ip_address` 非空且非 `group` 的设备，使用 `asyncio.Semaphore`（默认并发上限 100，可配置）并发探测。
- **ICMP**：使用 `ping3` 的异步能力或等价实现，超时默认 1 秒（可配置）。
- **TCP**：对配置了 `port` 的设备用 asyncio 建连探测，超时默认 2 秒（可配置）。
- **结果落库**：更新 `status`、`latency_ms`、`last_check`。
- **切换推送**：若某设备状态相对上次发生切换，向所有 WebSocket 客户端推送 `device_updated` 事件。
- **手动触发**：`POST /api/devices/{id}/recheck` 支持对单台设备及其子树立即巡检。

## 5. REST API

统一前缀 `/api`。错误格式：`{"detail": "..."}`，状态码 401/403/404/409/500。

### 5.1 认证与用户
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 公开 | 表单/JSON 登录，返回 JWT access token |
| GET | `/api/auth/me` | 登录 | 当前用户信息 |
| GET | `/api/users` | admin | 用户列表 |
| POST | `/api/users` | admin | 创建用户 |
| PUT | `/api/users/{id}` | admin | 更新用户（密码/角色） |
| DELETE | `/api/users/{id}` | admin | 删除用户（不允许删除自身） |

### 5.2 设备
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/devices/tree` | 登录 | 返回嵌套树 JSON（递归构建） |
| GET | `/api/devices` | 登录 | 扁平列表（分页 + 状态/类型筛选） |
| GET | `/api/devices/{id}` | 登录 | 单个节点（含子树统计） |
| POST | `/api/devices` | admin | 创建节点（root 或子节点） |
| PUT | `/api/devices/{id}` | admin | 更新节点 |
| DELETE | `/api/devices/{id}` | admin | 删除节点及子树 |
| POST | `/api/devices/{id}/recheck` | 登录 | 立即巡检该设备（含子树） |

### 5.3 设备树 JSON 形态（供 el-tree 直接绑定）
```json
{
  "id": 1,
  "name": "总部",
  "type": "group",
  "status": "unknown",
  "children": [
    {
      "id": 2,
      "name": "核心交换机",
      "type": "switch",
      "ip_address": "10.0.0.1",
      "status": "online",
      "latency_ms": 12,
      "last_check": "2026-08-05T10:00:00",
      "children": []
    }
  ]
}
```

## 6. WebSocket

- 端点：`GET /ws/status`，认证通过 URL query 携带 JWT（`?token=`），失败则关闭连接。
- 事件类型：
  - `device_updated`：单台设备状态/时延更新（含切换提醒，前端据此刷新树 + `el-notification` 告警）。
  - `device_offline`：`online→offline` 或 `warning→offline` 的切换告警（可并入 device_updated，由前端判断展示形式；设计保留独立类型便于扩展）。
  - `ping` / `pong`：心跳保活，30 秒间隔。
- 断线重连：前端指数退避自动重连；token 过期时跳回登录页。
- 兜底：前端在 WS 断开时启用 10 秒轮询 `GET /api/devices/tree`。

## 7. 前端

### 7.1 页面/视图
- `LoginView`：登录表单。
- `MainView`（主界面）：
  - 左侧：设备树（`el-tree`），顶部工具栏（新增根分组、刷新、状态筛选、online/offline 统计、全部展开/折叠）。
  - 节点自定义插槽：类型图标 + 状态圆点（绿=online、琥珀=warning、红=offline、灰=unknown）+ 名称 + IP + 最近巡检时间。
  - 右键上下文菜单：添加子节点 / 添加同级 / 编辑 / 删除（二次确认）/ 立即巡检。
- `UsersView`（admin）：用户列表与增删改、角色切换。

### 7.2 状态管理
- Pinia `auth` store：token 持久化（localStorage）、当前用户、登录/登出。
- Pinia `devices` store：树数据、加载/展开状态、状态筛选。
- WS 客户端收到 `device_updated` 时局部更新树节点，避免整树刷新。

### 7.3 构建与代理
- Vite dev server 将 `/api` 与 `/ws` 代理到后端（默认 `http://localhost:8000`）。
- 生产由 nginx 托管静态文件并反代 `/api` 与 `/ws` 到后端容器。

## 8. 角色权限矩阵

| 操作 | viewer | admin |
|---|---|---|
| 查看树 / 列表 / 状态 | ✔ | ✔ |
| 触发立即巡检 | ✔ | ✔ |
| 设备增删改 | ✘ | ✔ |
| 用户管理 | ✘ | ✔ |

## 9. 错误处理与健壮性

- 统一 JSON 错误；HTTP 语义正确（401 未认证、403 无权限、404 不存在、409 冲突、500 服务端）。
- ICMP 结果区分 `timeout`（离线）与协议 `error`（记为 `unknown` 或告警）。
- APScheduler 任务不重叠；巡检异常被捕获并记录日志，不影响后续周期。
- WS 连接管理：连接注册/注销、异常清理、心跳。
- 不允许 `parent_id` 指向自身或造成环；删除带子节点的节点需前端二次确认。

## 10. 测试策略

### 后端（pytest + httpx TestClient + 临时 SQLite）
- 单元：树构建递归函数、状态映射、`parent_id` 环校验。
- 接口：登录/鉴权/角色权限、设备 CRUD、recheck、用户管理。
- 引擎：用可注入的探测函数 mock 出 online/warning/offline 场景。
- 调度器：断言任务已注册、间隔参数正确（不真正等待周期）。

### 前端（Vitest，保持轻量）
- `DeviceTree` 渲染（不同状态圆点 class）、上下文菜单逻辑、`devices` store 的树更新 reducer。

## 11. 部署

### 11.1 本地开发（SQLite）
```
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # 使用默认 SQLite
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev                # http://localhost:5173
```

### 11.2 生产（Docker Compose，Linux）
- `docker-compose.yml`：`backend`（uvicorn :8000）+ `frontend`（nginx 托管 dist，反代 `/api`、`/ws`）+ `mysql:8`（:3306，数据卷持久化）。
- 环境变量：`WEAVER_DB_URL`（MySQL 连接串）、`WEAVER_JWT_SECRET`、`WEAVER_POLL_INTERVAL_MINUTES`、`MYSQL_ROOT_PASSWORD` 等，见 `.env.example`。
- 首次启动：后端自动建表，并创建默认 admin 账号（环境变量 `WEAVER_DEFAULT_ADMIN` / `WEAVER_DEFAULT_ADMIN_PASSWORD`）。

### 11.3 环境变量清单
| 变量 | 默认 | 说明 |
|---|---|---|
| WEAVER_DB_URL | `sqlite:///./weaver.db` | SQLAlchemy 连接串 |
| WEAVER_JWT_SECRET | 生成随机 | JWT 签名密钥 |
| WEAVER_TOKEN_EXPIRE_MINUTES | 480 | token 有效期 |
| WEAVER_POLL_INTERVAL_MINUTES | 5 | 巡检周期 |
| WEAVER_PING_CONCURRENCY | 100 | 并发探测上限 |
| WEAVER_PING_TIMEOUT | 1.0 | ICMP 超时（秒） |
| WEAVER_TCP_TIMEOUT | 2.0 | TCP 探测超时（秒） |
| WEAVER_DEFAULT_ADMIN | admin | 首次启动的默认管理员 |
| WEAVER_DEFAULT_ADMIN_PASSWORD | 强制设置 | 默认管理员密码 |

## 12. 验收标准（验证版）

1. 安装依赖后本地一条命令即可启动前后端；登录默认 admin 账号可进入主界面。
2. 可在树中创建分组与设备（含 IP、可选端口），编辑、删除（级联）正常。
3. 巡检引擎按配置周期运行，真实 IP（本机/网关）能正确标记 online/offline 并记录时延。
4. 手动"立即巡检"可用；单台设备可重新探测。
5. 状态切换时前端无需刷新即可看到更新并收到告警（WebSocket），断线后轮询兜底恢复。
6. admin 可创建 viewer 用户，viewer 无法进行增删改。
7. Docker Compose 一键起后端 + 前端 + MySQL，数据持久化。
