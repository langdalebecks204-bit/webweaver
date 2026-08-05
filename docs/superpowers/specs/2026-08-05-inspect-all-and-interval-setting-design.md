# WebWeaver 增强：立即巡检全部 + 巡检间隔自定义

## 背景

用户手工测试反馈：

1. 已巡检过的节点，后端 APScheduler 会自动巡检，前端 30 秒自动刷新后能看见延时变化（已确认生效）。
2. **新增节点不被自动巡检的感受**：调度器每 5 分钟会巡检所有有 IP 节点（含新增），但新增节点最多要等一个周期（5 分钟）才被检查，界面没有即时反馈。用户希望加一个「立即巡检全部」按钮。
3. 自动巡检间隔希望可自定义（界面设置、运行时生效、持久化）。

## 需求 1：立即巡检全部

- **后端**：`POST /api/devices/recheck-all`
  - 权限：`get_current_user`（admin + viewer 均可，与单节点 `recheck` 一致）。
  - 逻辑：查询所有 `ip_address is not null and type != "group"` 的设备，复用 `engine.run_inspection` 并发巡检，返回 `{"checked": [...]}`。
  - 把 `scheduler.py` 中 `scheduled_inspection` 的查询逻辑抽取为共享函数 `collect_all_targets(db) -> list[Device]`，调度器与接口复用，避免重复。
- **前端**：
  - `api/devices.js` 新增 `recheckAllDevices()` → `POST /devices/recheck-all`。
  - `stores/devices.js` 新增 action `recheckAll()`：调接口后 `load()` 刷新树。
  - `MainView.vue` 工具栏加「立即巡检全部」按钮（`el-button`，点击调 `store.recheckAll()`）。所有登录用户可见。

## 需求 2：巡检间隔自定义（仅 admin，运行时生效 + 持久化）

- **后端**：
  - `models.py` 新增 `Setting` 表（key-value）：`key`（PK，String）、`value`（String）。建表用现有 `Base.metadata.create_all`（需在 `init_db` import 新模型）。
  - 新 router `app/routers/settings.py`（prefix `/api/settings`）：
    - `GET /api/settings/inspection-interval`（admin）→ `{"poll_interval_minutes": int}`。取值优先级：DB > env 默认（`settings.poll_interval_minutes`）。
    - `PUT /api/settings/inspection-interval`（admin，body `{poll_interval_minutes: int}`，校验 1~1440）→ 写 DB（upsert），并调 `reschedule_interval()` 重排调度器作业；返回新值。
  - `inspector/scheduler.py`：
    - 新增模块级 `_scheduler` 引用 + `reschedule_interval(minutes)`（若 scheduler 存在则 `reschedule_job("inspection", trigger="interval", minutes=minutes)`）。
    - `create_scheduler()` 启动间隔改为读 DB（`get_poll_interval_from_db()`，缺省回退 `settings.poll_interval_minutes`）。
    - 新增 `collect_all_targets(db)` 共享查询。
  - `app/main.py`：注册 `settings.router`。
- **前端**：
  - `api/settings.js` 新增 `fetchInspectionInterval()` / `updateInspectionInterval(minutes)`。
  - `stores/settings.js` 新增 `useSettingsStore`（state `pollIntervalMinutes`，actions `loadInterval()`、`saveInterval(minutes)`）。
  - `MainView.vue` 工具栏（**仅 admin 可见**，`v-if="auth.user?.role === 'admin'"`）：数字输入（1~1440）+ 保存按钮；挂载时 `loadInterval()`。

## 校验与错误处理

- 间隔：`Field(ge=1, le=1440)`（pydantic 校验，超范围返回 422）。
- 前端保存间隔失败：`ElMessage.error(error.response?.data?.detail || '保存失败')`。
- 巡检全部失败：`ElMessage.error(...)`；成功后可提示或静默（自动刷新树即见状态）。

## 测试

- **后端**（`tests/`）：
  - `test_settings_api.py`（新）：GET 默认值（5）、PUT 后 GET 持久化新值、非 admin 403、超范围 422、重排调度器（mock `reschedule_interval` 被调）。
  - `test_scheduler.py` 扩展：`collect_all_targets` 过滤条件；`reschedule_interval` 对运行中调度器生效。
  - `test_devices_api.py` 扩展：`recheck-all` 返回所有有 IP 设备、viewer 可调、未登录 401。
- **前端**：
  - `stores/__tests__/settings.spec.js`（新）：`loadInterval` / `saveInterval` 调 API。
  - `views/__tests__/MainView.spec.js` 扩展：工具栏渲染「立即巡检全部」按钮；admin 显示间隔设置控件、viewer 不显示；保存调 `saveInterval`。
  - 回归：现有后端 38 + 前端 9 + `npm run build`。

## 改动文件

- 后端：`models.py`、`schemas.py`（可选）、`inspector/scheduler.py`、`routers/settings.py`（新）、`routers/devices.py`、`main.py`、`database.py`（init_db import）、`tests/*`。
- 前端：`api/settings.js`（新）、`api/devices.js`、`stores/settings.js`（新）、`stores/devices.js`、`views/MainView.vue`、测试。
