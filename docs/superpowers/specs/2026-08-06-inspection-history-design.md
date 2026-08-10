# WebWeaver 巡检历史记录 + 设备树横向滚动 设计文档

> 日期：2026-08-06

## 目标

1. 修复手机端设备树深层嵌套导致内容被截断的问题（加横向滚动）。
2. 新增巡检历史记录：每次巡检保存 Device 的延时/状态历史，支持按小时/按天平均延时的柱状图查询，辅助判断网络问题。

## 范围（用户已确认）

- **只记录设备树（Device）历史**，外网目标（ExternalTarget）暂不记录。
- **不做掉包率**（当前探针为单次 ICMP，无重发机制；掉包率需改探针为多次发送，复杂度高，本期搁置）。
- 柱状图按「单设备」查看：设备 Tab 右键 →「查看历史」→ 弹窗图表。
- 粒度可切换（按小时/按天），时间范围可选（默认 7 天：1/7/30 天）。
- 历史记录保留策略：自动清理 + 可配置保留天数（默认 30 天）。
- 图表库使用 **ECharts**。

## 决策记录

| 项 | 决策 |
|---|---|
| 记录粒度 | 每次巡检每个带 IP 的 Device 记一条 `{checked_at, status, latency_ms}` |
| 保留策略 | 清理超过 N 天记录；`probe_history_days`（默认 30），存 settings 表；每次巡检后顺带清理 |
| 设置接口 | `GET/PUT /api/settings/probe-history-days`（admin-only）；本期前端不做设置 UI |
| 查询 API | `GET /api/devices/{device_id}/history?days=7`（get_current_user，登录即可看） |
| 聚合方式 | 后端返回原始记录（按时间升序），前端 ECharts 做小时/天平均聚合 |
| 图表 | ECharts 柱状图，单设备，粒度切换（hour/day）+ 范围（1/7/30） |
| 入口 | DeviceTree 右键菜单新增「查看历史」 |
| 删除级联 | `device_id` 定义 `ondelete=CASCADE`，依赖 SQLite `PRAGMA foreign_keys=ON` 级联删除 |
| 横向滚动 | `el-tree` 外包 `.tree-scroll`（overflow-x:auto + min-width:max-content） |
| 备份/导入 | 历史记录不纳入备份/导入（仅设备/外网/设置） |

## 架构

### 数据模型（backend/app/models.py 新增）

```
ProbeRecord:
  id          int PK
  device_id   int FK -> devices.id (ondelete CASCADE), index
  checked_at  DateTime  (index, 清理/排序用)
  status      str  (online/warning/offline)
  latency_ms  int | None
```

### 记录写入（backend/app/inspector/engine.py）

`run_inspection` 中 `check_one` 每次探测完成后，除更新 `Device.status/latency_ms/last_check` 外，插入 `ProbeRecord(device_id, checked_at=utcnow(), status, latency_ms)`；`run_inspection` 现有的单个 `db.commit()` 一并提交。清理：同一 `run_inspection` 事务中 `DELETE FROM probe_records WHERE checked_at < now - history_days`（`history_days` 读取设置，一次 DELETE，成本低）。

### 历史查询（backend/app/routers/devices.py）

`GET /api/devices/{device_id}/history?days=7`
- `days`: `Query(default=7, ge=1)`；前端选项 1/7/30。路径段只有一段，与 `/{device_id}` 无路由冲突。
- 返回 `{"device_id": int, "records": [{"checked_at": iso, "status": str, "latency_ms": int|null}]}`
- 按 `checked_at` 升序。

### 设置（backend/app/routers/settings.py + services/setting_service.py）

- `setting_service.get_probe_history_days(db) -> int`：读 settings 表 `probe_history_days`，缺省 `settings.probe_history_days`（config 默认 30）。新增 `PROBE_HISTORY_DAYS_KEY` 常量（与现有 `POLL_INTERVAL_KEY` 风格一致）。
- `PUT /api/settings/probe-history-days` body `{"probe_history_days": int}`，范围 1-365，admin-only（与 `inspection-interval` 一致）。写入后不做其他动作（下次巡检清理生效）。GET 同样 admin-only。
- `config.py` 增加 `probe_history_days: int = 30`。

### 设备删除级联

`ProbeRecord.device_id` FK `ondelete="CASCADE"`；`delete_device_service` 用 bulk `DELETE`（`db.query(Device).where(...).delete()`），`database.py` 已对 SQLite 开 `PRAGMA foreign_keys=ON`，DB 层会级联删除 ProbeRecord。`conftest.py` 的 `clean_db` fixture 需把 `ProbeRecord` 加入清空列表。

### 前端

- **依赖**：`npm install echarts`。
- **MainView.vue**：`el-tree` 外包 `<div class="tree-scroll">`；CSS 加 `overflow-x:auto; overflow-y:hidden; -webkit-overflow-scrolling:touch; .el-tree{min-width:max-content}`。
- **DeviceTree.vue**：右键菜单加 `command="history"` → 触发 `history` 事件/打开弹窗。
- **新组件 DeviceHistory.vue**：
  - props: `device`（含 id/name）。
  - `el-dialog`，顶部粒度选择（小时/天）+ 时间范围（1/7/30）。
  - 拉取 `fetchDeviceHistory(deviceId, days)`。
  - ECharts 柱状图：hour → 每小时平均；day → 每天平均；空数据时段显示 0。
  - `window.resize` 时 `chart.resize()`。

### 前端 API/stores

- `frontend/src/api/devices.js` 新增 `fetchDeviceHistory(id, days)`（`client.get(\`/devices/${id}/history\`, { params: { days } })`）。
- `DeviceTree.vue`：右键菜单仅当 `props.node.ip_address` 存在时显示「查看历史」；`command="history"` → emit/open dialog。
- 新组件 `DeviceHistory.vue` 挂在 `MainView.vue`（`<DeviceHistory :device="historyDevice" />`），由 DeviceTree 通过事件上报选中的 device。

## 测试策略

- 后端：`test_history.py`（新）：
  - 写记录：`run_inspection` 后 `GET history` 返回该设备记录。
  - 过滤：`days` 生效（旧记录被排除/清理）。
  - 权限：viewer 可看 history。
  - 设备删除后 history 为空。
  - 清理：超过 `probe_history_days` 的记录被删。
- 前端：`DeviceHistory.spec.js`（new, happy-dom）：
  - 拉取并渲染图表（mock echarts + api）。
  - 切粒度/范围触发重新取数。
- 既有全量回归保持通过。

## 验收标准

1. 手机端打开设备 Tab，设备多/嵌套深时出现横向滚动条，可滑动查看。
2. 巡检运行后，`GET /api/devices/{id}/history` 返回历史记录。
3. 设备 Tab 右键某设备「查看历史」，弹窗显示 ECharts 柱状图；按小时/按天切换、1/7/30 天范围切换均生效。
4. 超过保留天数的记录被自动清理。
5. 删除设备后其历史记录一并删除。
6. 后端 pytest 全绿、前端 vitest 全绿、build 通过。
