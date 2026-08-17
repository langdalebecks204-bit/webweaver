# 交换机端口属性扩展设计

**日期：** 2026-08-17
**状态：** 已获用户批准

## 概述

为实现非管理型交换机"模拟端口亮灯"（见 `docs/2026-08-14-unmanaged-switch-port-led-design.md`），先扩展交换机设备的端口相关属性。LED 模拟 UI 为后续阶段，本轮只做数据层、API 与编辑 UI。

交换机分为两类：
- **管理型交换机**（`type == 'switch'`）：带 IP，支持 ICMP 探测。
- **非管理型交换机**（新增 `type == 'unmanaged_switch'`）：不带 IP，通过下级链路反推端口状态。

## 数据模型（后端）

### Device 模型新增三列

通过 `backend/app/database.py` 的 `_DEVICE_ADDED_COLUMNS` 迁移（SQLite ALTER TABLE ADD COLUMN）：

| 字段 | 列类型 | 默认 | 说明 |
|---|---|---|---|
| `port_count` | `Integer` | NULL | 端口总数（仅交换机类使用） |
| `uplink_port` | `Integer` | NULL | 上联端口号 |
| `port_bindings` | `JSON` | NULL | 端口号→`{target_id, type}` 映射 |

- `models.py`：`port_count: Mapped[int | None] = mapped_column(Integer, nullable=True)`；`uplink_port` 同理；`port_bindings: Mapped[dict | None] = mapped_column(JSON, nullable=True)`。
- `database.py` `_DEVICE_ADDED_COLUMNS` 追加：`"port_count": "INTEGER"`、`"uplink_port": "INTEGER"`、`"port_bindings": "TEXT"`（SQLite JSON 以 TEXT 存储）。

### 设备类型

- `backend/app/services/device_types.py` `BUILTIN_TYPES` 追加 `"unmanaged_switch"`。
- `frontend/src/utils/deviceTypes.js`：
  - `DEVICE_TYPE_LABELS` 追加 `unmanaged_switch: '非管理型交换机'`
  - `DEVICE_TYPE_ICONS` 追加 `unmanaged_switch: 'Connection'`（与 switch 相同图标）

## API 与校验

### Schemas（`backend/app/schemas.py`）

新增子模型：

```python
class PortBinding(BaseModel):
    target_id: int
    type: Literal["uplink", "downlink"]
```

`DeviceBase`/`DeviceCreate`/`DeviceUpdate` 追加：

```python
port_count: int | None = Field(default=None, ge=1, le=48)
uplink_port: int | None = Field(default=None, ge=1, le=48)
port_bindings: dict[str, PortBinding] | None = None
```

`DeviceOut`/`device_to_dict` 输出新字段。

### 校验逻辑（服务层 `device_service.py`）

`create_device`/`update_device` 中，仅当 `type` 为交换机类（`switch`/`unmanaged_switch`）时处理端口字段：

1. **非交换机类型静默丢弃**：端口字段不保存（从 `model_dump` 中剔除）。
2. **端口号范围**：`port_bindings` 的每个 key 必须在 `1..port_count` 内（若 `port_count` 有值）；key 必须为数字字符串 `"1".."48"`。
3. **target 存在**：每个绑定的 `target_id` 必须指向存在的设备，否则 `ValueError` → HTTP 409。
4. `uplink_port` 与 `port_bindings` 无强制关系（仅端口号范围校验），上联口可同时出现在绑定中。

### 序列化

`device_to_dict` 追加三字段；`port_bindings` 原样输出 dict。

## 前端编辑 UI

### 设备编辑弹窗（`MainView.vue` 现有 `deviceDialog`）

当 `deviceForm.type === 'switch' || deviceForm.type === 'unmanaged_switch'` 时额外显示：

- **端口总数**：`el-input-number`（1-48）
- **上联端口**：`el-input-number`（1-48）
- **端口绑定按钮**："配置端口绑定" → 打开独立弹窗

非交换机类型不显示上述控件。

### 独立端口绑定弹窗（新组件 `PortBindingDialog.vue`）

**Props：** `modelValue: boolean`、`portCount: number`、`bindings: object`、`childDevices: array`（仅直接子节点，含 id/name）

**Emits：** `update:modelValue`、`save(bindings: object)`

**交互：**
- 按 `portCount` 渲染端口行（1..portCount）。
- 每行：端口号（固定显示）+ 绑定设备选择（`el-select`，选项为 `childDevices`）+ 类型选择（`el-select`：下联/上联）+ 清除按钮。
- 保存时组装 `port_bindings` dict，仅保留绑定了设备的端口项。
- 外部保存：MainView 中 `onSaveDevice` 前将弹窗结果写入 `deviceForm.port_bindings`。

**校验：** 端口号范围在弹窗内由 `portCount` 天然保证。

## 备份与恢复

- `backup_service.py` `_flatten_devices` 导出追加 `port_count`/`uplink_port`/`port_bindings`。
- `_import_devices` 导入读取三字段（`device = Device(...)` 追加），旧备份缺字段时安全（`.get()` 返回 None）。
- `BACKUP_VERSION` 保持 2（兼容旧备份，新字段可选）。

## 文件变更清单

| 文件 | 变更 |
|---|---|
| `backend/app/models.py` | 三列 |
| `backend/app/database.py` | 迁移列 |
| `backend/app/schemas.py` | PortBinding + 字段 + DeviceOut |
| `backend/app/services/device_service.py` | 校验 + 序列化 |
| `backend/app/services/device_types.py` | BUILTIN_TYPES |
| `backend/app/services/backup_service.py` | 导出/导入 |
| `frontend/src/utils/deviceTypes.js` | unmanaged_switch 标签/图标 |
| `frontend/src/components/PortBindingDialog.vue` | 新组件 |
| `frontend/src/views/MainView.vue` | 端口字段 + 弹窗集成 |
| 后端测试 | 字段/校验/备份/unmanaged_switch |
| 前端测试 | PortBindingDialog + MainView 端口字段 |

## 测试要点

**后端：**
- create/update 交换机设备保存 port_count/uplink_port/port_bindings，读出一致
- 端口号超出 1..port_count 范围 → 409
- target_id 不存在 → 409
- 非交换机类型带端口字段 → 静默丢弃（不保存）
- `unmanaged_switch` 是合法类型
- 备份导出含三字段，导入恢复，旧备份（无字段）导入成功

**前端：**
- PortBindingDialog：按 portCount 渲染端口行；选择子设备+类型组装 dict；仅保留绑定项
- MainView：交换机类显示端口字段与"配置端口绑定"；非交换机类隐藏
- deviceTypes：unmanaged_switch 有标签与图标