# 用户管理 + 数据备份导入导出 设计规格

**日期:** 2026-08-06
**范围:** 前端用户管理界面；设备/外网目标/巡检间隔的备份导出与导入；清除所有数据（初始化）。

## 目标

1. 提供管理员用户管理界面（后端 `/api/users` CRUD 已存在，补齐前端）。
2. 提供备份导出/导入：设备 + 外网目标 + 巡检间隔设置，导出时可单独勾选类别；导入时可选「替换」或「合并」。
3. 提供「清除所有数据（初始化）」：清空设备/外网/设置/用户，仅重建默认 admin（admin/admin123）。

## 现状

- 后端 `backend/app/routers/users.py`：`/api/users` 全套 CRUD（admin-only；自删 409；可改角色/密码）。
- 前端：Vue3 + Pinia + Element Plus；MainView 用 `el-tabs`（设备/外网）；有 devices/external/settings/auth store；无 users store/api、无备份功能。
- 数据表：devices、external_targets、users、settings；SQLite（`weaver.db`）。
- 角色：admin / viewer。

## 后端设计

### 路由 `backend/app/routers/backup.py`（prefix=`/api/backup`，全部 `require_admin`）

**导出** `GET /api/backup/export`
- 查询参数 `include_devices`、`include_external`、`include_settings`（布尔）。
- 未传任何参数 → 默认全包含；传了则按标记选择。
- 返回 JSON：`{"version": 1, "exported_at": <ISO>, "devices": [...], "external": [...], "settings": [...]}`，未选类别省略。
  - devices：按「父在前、子在后」顺序（遍历树）；每项 `{name, type, ip_address, port, order_index, parent_id}`，`parent_id` 为备份内本地 id。
  - external：`{name, ip_address, domain, port}`。
  - settings：`[{key, value}]`。
  - 不含用户账号与实时运行态（status/last_check 等）。

**导入** `POST /api/backup/import?mode=replace|merge`（multipart 上传 JSON 文件）
- 校验：JSON 合法；`version` 存在且 `== 1`；必填字段（devices 的 name 等）齐全 → 否则 422。
- **replace**：单事务内清空 `Device/ExternalTarget/Setting`，再按备份重建；用「旧 id → 新 id」映射恢复 `parent_id` 层级。
- **merge**：设备按**同名则跳过**（不覆盖），新设备按「父设备名」挂载（父不存在则挂根）；外网目标**同名跳过**；设置按备份值覆盖。
- 若导入含 settings → 调用 `reschedule_interval(...)` 同步运行中调度器。

**清除所有数据** `POST /api/backup/reset`
- 单事务清空 `Device/ExternalTarget/Setting/User`，`seed_default_admin()` 重建默认 admin，恢复默认巡检间隔并 `reschedule_interval(...)`。

### 错误处理
- 所有导入/重置用单事务；校验失败整体回滚，绝不半导入。
- 非法 JSON → 400/422（带 detail）；不支持的 version → 422。

## 前端设计

### 路由/视图
- MainView `el-tabs` 变为：设备 / 外网 / 用户管理 / 备份与恢复。后两者仅 admin 可见（viewer 隐藏）。
- 新增组件 `UsersPanel.vue`、`BackupPanel.vue`，避免 MainView 膨胀。

### `UsersPanel.vue`（用户管理）
- 表格：用户名 / 角色(tag) / 创建时间 / 操作（编辑、删除）。
- 「新增用户」弹窗：用户名 + 密码(min6) + 角色下拉。
- 「编辑」弹窗：改角色 + 可选重置密码（留空不更密）。
- 删除前确认；自删被后端 409 拒绝时提示错误。

### `BackupPanel.vue`（备份与恢复）
- 导出区：勾选「设备 / 外网目标 / 巡检间隔」（默认全选）+「导出备份」→ `client.get('/backup/export',{params})`，用 Blob 下载 `weaver-backup-<时间戳>.json`。
- 导入区：文件选择 + 模式单选（替换/合并）+「导入」→ FormData 上传 + `mode`；成功后刷新设备树/外网/间隔。
- 危险区：「清除所有数据（初始化）」——二次确认弹窗（输入确认词），成功后提示重新登录并跳转登录页（用户被重置）。

### 前端 API/Store
- 新增 `src/api/users.js`（fetchUsers/createUser/updateUser/deleteUser）。
- 新增 `src/stores/users.js`（state: users/loading；actions: load/create/update/remove）。
- 新增 `src/api/backup.js`（exportBackup/importBackup/resetData）。

## 权限
- 备份/恢复/重置、用户管理：admin-only（后端 `require_admin`，非 admin → 403）；前端隐藏对应页签。
- 现有设备/外网读取保持登录即可。

## 测试

### 后端 `backend/tests/test_backup_api.py`
- export 默认含全部类别；`include_*` 可仅选子集。
- export → import(replace) 往返保持设备树结构、外网、设置。
- import(merge) 不重复同名；新增缺失项。
- 非法 JSON / version≠1 → 422。
- reset 清空设备/外网/设置/用户，重建 admin（admin/admin123 可登录）。
- 三接口均 admin-only（viewer → 403）。
- 含 settings 导入时 mock 到 `reschedule_interval` 被调用。

### 前端
- `src/stores/__tests__/users.spec.js`、`src/components/__tests__/UsersPanel.spec.js`、`src/components/__tests__/BackupPanel.spec.js`。
- 覆盖：列表/新增/编辑/删除/viewer 隐藏；导出勾选参数传递；导入文件+模式；清除需输入确认词。