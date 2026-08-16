# 设备类型收起 + ICMP ping 自定义设计

**日期：** 2026-08-16
**状态：** 已获用户批准

## 概述

两个独立功能：

1. **设备类型收起**：`MainView.vue` 设备页工具栏中的设备类型管理区（内置/自定义类型标签 + 添加输入框）当前占一整行，改为默认收起的折叠面板，工具栏只保留"设备类型"按钮，点击内联展开。
2. **ICMP ping 自定义**：ICMP 巡检目前单次 ping（失败即离线），改为可配置的多次 ping 与包大小，全局设置、保存即生效。

两者互不依赖，可独立实施与测试。

---

## 需求 1：设备类型收起

### 现状

`MainView.vue:275-302`，`.type-manage` 区块内嵌在设备页卡片 header 的 `.toolbar` 中，含：
- 内置类型标签（`settings.builtinTypes`，带"（内置）"后缀）
- 自定义类型标签（`settings.customTypes`，带 closable 删除）
- 自定义类型名输入框 + "添加"按钮

仅管理员可见（`v-if="isAdmin"`）。当前占用工具栏一整行，挤压树形/表格切换等控件。

### 设计

- 新增 `ref` 状态 `typesExpanded`（默认 `false`）。
- 工具栏中 `.type-manage` 区块改为：一个"设备类型" toggle 按钮（`isAdmin` 时显示），点击切换 `typesExpanded`。
- 展开时内联显示原标签 + 输入框 + 添加按钮，用 Element Plus `el-collapse-transition` 包裹做展开/收起动画（高度自适应，无固定高度）。
- 收起时工具栏只保留"设备类型"按钮（可加角标/箭头指示状态，如"设备类型 ▾"）。
- 内容与交互完全复用现有 `onAddCustomType` / `onRemoveCustomType`，无逻辑变更。

### 交互细节

- 默认收起。
- 展开后布局：按钮仍在工具栏行，下方新起一行显示完整类型管理内容（flex-wrap 换行），避免横向挤压。
- 添加/删除成功后自动刷新类型列表（现有 `settings.addType`/`removeType` 已内部重新 `loadTypes`）。

### 测试要点

- admin：默认不显示标签内容，点击"设备类型"按钮后显示内置/自定义标签与添加输入框；再次点击收起。
- admin：展开后添加自定义类型仍调用 `addType`，删除仍调用 `removeType`（复用现有测试逻辑，先展开再断言）。
- viewer：不显示"设备类型"按钮，标签内容也不可见。

---

## 需求 2：ICMP ping 自定义

### 现状

- `engine.py:27-34` `icmp_ping(host, timeout)` 单次调用 `async_ping(host, timeout, unit="ms")`，返回单次延时或 `None`。
- `engine.py:49-59` `probe_device`：`icmp_ping` 返回 `None` → 判 `offline`；否则按 TCP 探活决定 `online`/`warning`。
- `config.py`：`ping_timeout`（默认 1.0s）、`ping_concurrency`（100）为环境变量，本次不改。
- 设置持久化模式：`setting_service.py` 用 `Setting` 键值表（`poll_interval_minutes`、`probe_history_days` 已有先例），API 在 `routers/settings.py`，admin-only。

### 设计

#### 新增配置键

| 键 | 含义 | 范围 | 默认 |
|---|---|---|---|
| `ping_count` | 每次巡检 ICMP ping 次数 | 1–10 | 3 |
| `ping_packet_size` | ICMP 包大小（字节） | 32–10000 | 56 |

存储于 `Setting` 表，`setting_service.py` 新增 `get_ping_params(db) -> tuple[int, int]` / `set_ping_params(db, count, size)`。

#### 后端 API（`routers/settings.py`）

仿 `inspection-interval` 模式，admin-only：

- `GET /api/settings/ping-params` → `{"ping_count": 3, "ping_packet_size": 56}`
- `PUT /api/settings/ping-params` body `{"ping_count": int, "ping_packet_size": int}` → 校验范围后持久化返回

校验：`ping_count` 1–10（`ge=1, le=10`），`ping_packet_size` 32–10000（`ge=32, le=10000`）。范围由 Pydantic Field 校验（422 自动返回），无需额外逻辑。

#### 引擎修改（`engine.py`）

- `icmp_ping(host, timeout, count, packet_size)` 改为循环发送：
  - 每次 `async_ping(host, timeout=timeout, size=packet_size, unit="ms")`。
  - 收集成功延时列表。
  - 成功次数 `> count // 2`（超过半数）视为在线，延时取成功次平均值 `int(round(sum/len))`；否则返回 `None`。
- 例：count=3 需成功 ≥2；count=2 需成功 ≥2（`2 // 2 = 1`，需 `> 1` 即 2）；count=1 需成功 ≥1。
- `probe_device` 与 `run_inspection` / `run_external_inspection` 在巡检时读取当前 `ping_params` 传入。为避免每次设备都查 DB，由 `run_inspection` 入口读取一次，逐设备传入 `probe_device`。

签名变化：
```
probe_device(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size)
icmp_ping(host, timeout, count, packet_size)
```
`run_inspection(db, devices)` 与 `run_external_inspection(db, targets)` 开头各读一次 `get_ping_params(db)`。

#### 前端

- `api/settings.js`：新增 `fetchPingParams()`、`updatePingParams(count, size)`。
- `stores/settings.js`：state 新增 `pingCount: 3`、`pingPacketSize: 56`；actions 新增 `loadPingParams()`、`savePingParams()`。
- `MainView.vue`：
  - `onMounted` 中（admin）调用 `settings.loadPingParams()`（与 `loadInterval` 并列）。
  - 工具栏 `.interval-setting` 旁新增巡检参数控件（仅 admin）："ping次数" `el-input-number`（1–10）+ "包大小" `el-input-number`（32–10000）+ "保存巡检参数"按钮，复用 `保存间隔` 的保存/错误提示模式。
  - 保存成功 `ElMessage.success('已保存')`；失败显示后端 detail。

### 交互细节

- 保存即生效：下次巡检（含手动"立即巡检全部"）即用新值，无需重启。scheduler 巡检每次读取 DB，天然生效。
- 对外网目标同样生效（`run_external_inspection` 共用 `probe_device`）。

### 测试要点

后端（`tests/test_engine.py`）：
- `icmp_ping`：3 次中 2 成功 → 返回平均值；1 成功 → 返回 `None`（未超半数）；验证 `size` 参数被传入 `async_ping`。
- `probe_device`：传入 count=3，mock `icmp_ping` 返回平均值，现有 online/warning/offline 用例适配新签名。
- 设置 API（`tests/test_settings_api.py`）：GET 返回默认 3/56；PUT 持久化；范围越界 422；admin-only（viewer 403）。

前端（`MainView.spec.js`、`stores/settings.spec.js`）：
- settings store：`loadPingParams`/`savePingParams` 调用 API 并更新 state。
- MainView：admin 显示次数/包大小输入框与"保存巡检参数"，保存调用 `savePingParams`；viewer 不显示。

---

## 错误处理

- 设置 API 范围校验由 Pydantic 处理，越界返回 422（前端 ElMessage 显示后端 detail）。
- ping 全部超时/未超半数 → `icmp_ping` 返回 `None` → 设备判 `offline`（现有逻辑不变）。
- `async_ping` 抛异常 → 单次计为失败，不中断整体巡检。

## 不做的事（YAGNI）

- 不做每设备单独 ping 参数（需求已确认全局）。
- 不改 `ping_timeout`/`ping_concurrency`（保持环境变量配置）。
- 不做 ping 参数历史记录或图表。
- 设备类型收起不做持久化记忆（刷新后恢复默认收起）。

## 文件变更清单

| 文件 | 变更 |
|---|---|
| `frontend/src/views/MainView.vue` | 类型收起折叠 + ping 参数控件 |
| `frontend/src/stores/settings.js` | ping 参数 state/actions |
| `frontend/src/api/settings.js` | fetch/update ping params |
| `backend/app/services/setting_service.py` | get/set_ping_params |
| `backend/app/routers/settings.py` | GET/PUT ping-params |
| `backend/app/inspector/engine.py` | icmp_ping 多次+size，probe_device 签名 |
| `frontend/src/views/__tests__/MainView.spec.js` | 类型收起 + ping 参数测试 |
| `frontend/src/stores/__tests__/settings.spec.js` | ping 参数 store 测试 |
| `backend/tests/test_engine.py` | icmp_ping 多次/半数/size 测试，probe_device 适配 |
| `backend/tests/test_settings_api.py` | ping-params API 测试 |