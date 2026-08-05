# WebWeaver 增强：带 IP 即巡检 + 外网目标检测

## 背景

1. **带 IP 的分组设备不被巡检**：用户添加 PVE1、istoreos、centos7、FnOS 等设备时类型选为 `group` 但填了真实 IP+端口，由于巡检目标过滤条件为 `ip_address 非空 AND type != "group"`，这些节点从不被巡检（数据库证据：`last_check` 为空）。用户确认：**任何有 IP 的设备都应被巡检**，`group` 只是组织树结构，不影响探测。
2. **需要外网检测**：新增独立的「外网目标」列表，目标含名称 + 可选 IP + 可选域名，IP 与域名分开检测、分开显示结果。若域名存在则域名与 IP 都检测。

## 范围

- 后端：巡检过滤修复 + 外网目标模型/CRUD API/检测引擎/调度整合。
- 前端：MainView 加 Tab（设备/外网），外网目标列表 CRUD 与检测，30 秒轮询同步刷新。

## 需求 1：带 IP 即巡检（修复）

- `collect_all_targets`（`backend/app/inspector/scheduler.py`）过滤条件改为仅 `Device.ip_address.is_not(None)`，去掉 `Device.type != "group"`。
- 单节点 recheck（`backend/app/routers/devices.py` 的 `recheck_device`）同样去掉 `Device.type != "group"` 条件。
- 无 IP 的设备（任何类型）仍不巡检。

## 需求 2：外网目标

### 数据模型 `ExternalTarget`（`backend/app/models.py` 新增 `external_targets` 表）

- `id: int` PK
- `name: str`（String(100)，必填）
- `ip_address: str | None`（String(45)）
- `domain: str | None`（String(255)）
- `port: int | None`（1~65535）
- `ip_status: str`（default "unknown"）、`ip_latency_ms: int | None`、`ip_last_check: datetime | None`
- `domain_status: str`（default "unknown"）、`domain_latency_ms: int | None`、`domain_last_check: datetime | None`
- `created_at` / `updated_at`（复用 `utcnow`）

校验：`name` 非空；`ip_address` 与 `domain` 至少一个非空（pydantic `model_validator`，422）。

### 检测逻辑（`backend/app/inspector/engine.py` 新增 `run_external_inspection(db, targets)`）

- 复用 `asyncio.Semaphore(settings.ping_concurrency)` 与 `probe_device`。
- 对每个目标并行：
  - **IP 探测**：仅当 `ip_address` 非空 —— 调 `probe_device(ip_address, port, ping_timeout, tcp_timeout)`，写 `ip_status/ip_latency_ms/ip_last_check`。
  - **域名探测**：仅当 `domain` 非空 —— `asyncio.wait_for(asyncio.getaddrinfo(domain, None), timeout=settings.ping_timeout)` 取首个地址；解析失败 → `offline`；解析成功 → 对解析出的 IP 调 `probe_device(resolved_ip, port, ...)`，写 `domain_status/domain_latency_ms/domain_last_check`。
- 全部完成后 `db.commit()`，返回 `list[dict]`（`external_target_to_dict`）。

### API（`backend/app/routers/external.py` 新增，prefix `/api/external`）

- `GET ""` — `get_current_user`，返回列表。
- `POST ""`（201）— `require_admin`，创建；校验失败 422。
- `PUT /{id}` — `require_admin`；404 if missing。
- `DELETE /{id}` — `require_admin`；返回 `{"deleted": id}`。
- `POST /check-all` — `get_current_user`，`run_external_inspection` 全部目标，返回 `{"checked": [...]}`。

### 调度整合

- `backend/app/inspector/scheduler.py`：
  - 新增 `collect_external_targets(db) -> list[ExternalTarget]`（全部目标）。
  - `scheduled_inspection` 同时运行 `run_inspection(db, devices)` 与 `run_external_inspection(db, targets)`。
- `backend/app/routers/devices.py` 的 `recheck_all_devices`：同时检测设备与外网目标，返回 `{"checked": [...], "external_checked": [...]}`。

### 前端

- `frontend/src/api/external.js`（新）：`fetchExternalTargets()`、`createExternalTarget(payload)`、`updateExternalTarget(id, payload)`、`deleteExternalTarget(id)`、`checkAllExternalTargets()`。
- `frontend/src/stores/external.js`（新）：state `targets`、getters 无、actions `load()`、`create()`、`update()`、`remove()`、`checkAll()`（调接口后 `load()`）。
- `frontend/src/views/MainView.vue`：
  - 用 `el-tabs` 分「设备」「外网」两个面板。
  - 设备面板：现有工具栏（新增根分组/刷新/立即巡检全部/仅 admin 间隔设置）+ 设备树。「立即巡检全部」触发 `store.recheckAll()`（设备）+ `externalStore.checkAll()`（外网）。
  - 外网面板：工具栏（admin 可见「新增外网目标」；「刷新」；「立即检测」触发 `externalStore.checkAll()`）+ 表格（名称 / IP / IP 状态+延时 / 域名 / 域名状态+延时 / 操作[编辑、删除，仅 admin 可见]）。
  - 30 秒轮询同时 `store.load()` 与 `externalStore.load()`。

## 校验与错误处理

- 外网目标 `name` 空 / IP 与域名均空 → 422。
- `port` 越界 → 422（pydantic Field ge=1 le=65535）。
- 删除/编辑不存在的目标 → 404。
- 前端错误提示沿用 `ElMessage.error(error.response?.data?.detail || '操作失败')`。
- 域名解析失败视为该域名的探测结果 `offline`（并写入 `domain_last_check`）。

## 测试

- **后端**：
  - `tests/test_scheduler.py`：`test_collect_all_targets_filters` 改为期望分组含 IP 也被收集（`["sub","sw1","sw2"]`）；新增 `test_collect_external_targets_returns_all`。
  - `tests/test_devices_api.py`：`test_recheck_all_devices` 断言分组含 IP 也在 `checked` 中；`recheck-all` 响应含 `external_checked` 键；`recheck_device`（单节点）对 group+IP 返回结果。
  - `tests/test_external_api.py`（新）：CRUD、权限（viewer 403 写 / 200 读）、校验 422、`check-all` 返回全部且结果写入（monkeypatch `probe_device` 与 `getaddrinfo`）。
  - `tests/test_engine.py`：`run_external_inspection` 对 IP-only / domain-only / 两者皆有的目标正确写字段（monkeypatch `probe_device`、`getaddrinfo`）。
- **前端**：
  - `stores/__tests__/external.spec.js`（新）：`load`/`create`/`update`/`remove`/`checkAll` 调 API。
  - `views/__tests__/MainView.spec.js`：Tab 渲染、外网表格渲染、外网新增/立即检测按钮（admin/viewer 区分）、「立即巡检全部」同时触发设备与外网。

## 改动文件

- 后端：`models.py`、`schemas.py`、`services/external_service.py`（新）、`inspector/engine.py`、`inspector/scheduler.py`、`routers/external.py`（新）、`routers/devices.py`、`main.py`、`database.py`（init_db import）、`tests/*`。
- 前端：`api/external.js`（新）、`stores/external.js`（新）、`stores/devices.js`（`recheckAll` 响应兼容）、`views/MainView.vue`、测试。
