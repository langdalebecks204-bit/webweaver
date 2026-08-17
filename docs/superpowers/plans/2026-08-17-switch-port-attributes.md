# 交换机端口属性扩展实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为交换机设备（`switch`/`unmanaged_switch`）扩展端口属性 `port_count`/`uplink_port`/`port_bindings`，新增 `unmanaged_switch` 类型，并提供编辑 UI（独立端口绑定弹窗）。LED 模拟为后续阶段。

**Architecture:** 后端新增三个 Device 列（SQLite 迁移），schema 用 `PortBinding` 子模型校验，服务层对交换机类校验端口范围与 target 存在性、非交换机类静默丢弃。前端新增 `PortBindingDialog.vue` 组件，MainView 编辑弹窗按类型显示端口字段。备份导出/导入含新字段。

**Tech Stack:** Vue 3 `<script setup>`、Pinia、Element Plus、vitest + happy-dom、FastAPI、Pydantic v2、SQLAlchemy 2、pytest。

## Global Constraints

- `port_count`/`uplink_port` 范围 1–48，仅交换机类（`switch`/`unmanaged_switch`）生效。
- 非交换机类型携带端口字段 → 服务层静默丢弃（不保存）。
- `port_bindings` 为 `dict[str, PortBinding]`，key 为数字字符串端口号，value 为 `{target_id: int, type: "uplink"|"downlink"}`。
- `port_bindings` key 必须在 `1..port_count` 内（port_count 有值时），target_id 必须存在。
- 上联口与绑定无强制关系（仅端口号范围校验）。
- 绑定对象仅限当前设备的**直接子节点**。
- 备份版本保持 2（新字段可选，旧备份兼容）。
- 修改含中文文件必须用 Edit 工具，禁止 PowerShell `Set-Content`。

---

### Task 1: 后端模型 + 迁移 + unmanaged_switch 类型

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/services/device_types.py`
- Test: `backend/tests/test_device_types.py`

**Interfaces:**
- Produces: `Device.port_count: int | None`、`Device.uplink_port: int | None`、`Device.port_bindings: dict | None`（JSON 列）；`BUILTIN_TYPES` 含 `"unmanaged_switch"`；迁移自动加三列。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_device_types.py` 追加：

```python
def test_unmanaged_switch_is_builtin():
    assert "unmanaged_switch" in dt.BUILTIN_TYPES
```

（文件已有 `from app.services import device_types as dt`。）

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_device_types.py -q`（backend 目录）
Expected: FAIL（`unmanaged_switch` 不在 BUILTIN_TYPES）。

- [ ] **Step 3: 模型加列**

`backend/app/models.py` 在 `image_url` 后追加：

```python
    port_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uplink_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    port_bindings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

import 追加 `JSON`：`from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String`。

- [ ] **Step 4: 迁移加列**

`backend/app/database.py` `_DEVICE_ADDED_COLUMNS` 追加：

```python
    "port_count": "INTEGER",
    "uplink_port": "INTEGER",
    "port_bindings": "TEXT",
```

- [ ] **Step 5: 类型列表加 unmanaged_switch**

`backend/app/services/device_types.py` `BUILTIN_TYPES` 追加 `"unmanaged_switch"`。

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_device_types.py -q`（backend 目录）
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/app/models.py backend/app/database.py backend/app/services/device_types.py backend/tests/test_device_types.py
git commit -m "feat: add switch port columns and unmanaged_switch type"
```

---

### Task 2: schema + 服务层校验与序列化

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/device_service.py`
- Test: `backend/tests/test_devices_api.py`

**Interfaces:**
- Consumes: `Device.port_count`/`uplink_port`/`port_bindings`（Task 1 产出）。
- Produces: `PortBinding` 子模型；`DeviceCreate`/`DeviceUpdate`/`DeviceOut` 含新字段；`device_to_dict` 输出新字段；`create_device`/`update_device` 校验。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_devices_api.py` 追加：

```python
def test_create_switch_with_ports(client, admin_headers):
    r = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "unmanaged_switch", "port_count": 8,
              "uplink_port": 1,
              "port_bindings": {"1": {"target_id": 99, "type": "uplink"}}},
    )
    assert r.status_code == 409  # target 99 不存在
```

先验证类型合法与序列化（单独创建无绑定的）：

```python
def test_create_unmanaged_switch_serializes_ports(client, admin_headers):
    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "unmanaged_switch", "port_count": 8, "uplink_port": 1},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["port_count"] == 8
    assert body["uplink_port"] == 1
    assert body["port_bindings"] is None

    got = client.get(f"/api/devices/{body['id']}", headers=admin_headers)
    assert got.json()["port_count"] == 8
    assert got.json()["uplink_port"] == 1
```

（`test_create_switch_with_ports` 中 target 99 校验需在服务层实现后通过，先一并写出。）

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_devices_api.py -k "unmanaged_switch or switch_with_ports" -q`（backend 目录）
Expected: FAIL（`port_count` 不是合法字段 → 422）。

- [ ] **Step 3: schema 加字段**

`backend/app/schemas.py` 顶部 import 追加 `Literal`：`from typing import Literal`。新增：

```python
class PortBinding(BaseModel):
    target_id: int
    type: Literal["uplink", "downlink"]
```

`DeviceBase` 追加：

```python
    port_count: int | None = Field(default=None, ge=1, le=48)
    uplink_port: int | None = Field(default=None, ge=1, le=48)
    port_bindings: dict[str, PortBinding] | None = None
```

`DeviceUpdate` 追加（含 `port_bindings: dict[str, PortBinding] | None = None`）。

- [ ] **Step 4: 服务层序列化 + 校验**

`backend/app/services/device_service.py` `device_to_dict` 追加：

```python
        "port_count": d.port_count,
        "uplink_port": d.uplink_port,
        "port_bindings": d.port_bindings,
```

新增辅助函数（放 `is_valid_type` import 后）：

```python
_SWITCH_TYPES = {"switch", "unmanaged_switch"}


def _validate_port_fields(db: Session, data: dict, port_count: int | None) -> None:
    bindings = data.get("port_bindings")
    if not bindings:
        return
    for key, binding in bindings.items():
        if not key.isdigit():
            raise ValueError("port binding key must be numeric")
        port = int(key)
        if port_count is not None and (port < 1 or port > port_count):
            raise ValueError(f"port {port} out of range 1..{port_count}")
        if db.get(Device, binding["target_id"]) is None:
            raise ValueError(f"port binding target {binding['target_id']} not found")
```

`create_device` 中，`model_dump` 后：

```python
    payload = data.model_dump()
    if data.type in _SWITCH_TYPES:
        _validate_port_fields(db, payload, payload.get("port_count"))
    else:
        payload.pop("port_count", None)
        payload.pop("uplink_port", None)
        payload.pop("port_bindings", None)
    device = Device(**payload)
```

`update_device` 中，`changes = data.model_dump(exclude_unset=True)` 后：

```python
    if changes.get("type", device.type) in _SWITCH_TYPES:
        _validate_port_fields(db, changes, changes.get("port_count", device.port_count))
    else:
        changes.pop("port_count", None)
        changes.pop("uplink_port", None)
        changes.pop("port_bindings", None)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_devices_api.py -k "unmanaged_switch or switch_with_ports" -q`（backend 目录）
Expected: PASS。

- [ ] **Step 6: 追加校验测试**

在 `backend/tests/test_devices_api.py` 追加：

```python
def test_switch_port_bindings_roundtrip(client, admin_headers):
    target = client.post("/api/devices", headers=admin_headers,
                         json={"name": "T", "type": "terminal", "ip_address": "1.1.1.1"}).json()
    sw = client.post("/api/devices", headers=admin_headers,
                     json={"name": "SW", "type": "switch", "port_count": 8,
                           "port_bindings": {"2": {"target_id": target["id"], "type": "downlink"}}})
    assert sw.status_code == 201
    body = sw.json()
    assert body["port_bindings"]["2"]["target_id"] == target["id"]

    upd = client.put(f"/api/devices/{body['id']}", headers=admin_headers,
                     json={"port_bindings": {"3": {"target_id": target["id"], "type": "downlink"}}})
    assert upd.status_code == 200
    assert upd.json()["port_bindings"]["3"]["target_id"] == target["id"]


def test_switch_port_out_of_range(client, admin_headers):
    r = client.post("/api/devices", headers=admin_headers,
                    json={"name": "SW", "type": "switch", "port_count": 4,
                          "port_bindings": {"5": {"target_id": 1, "type": "downlink"}}})
    assert r.status_code == 409


def test_non_switch_drops_port_fields(client, admin_headers):
    r = client.post("/api/devices", headers=admin_headers,
                    json={"name": "TERM", "type": "terminal", "port_count": 8, "uplink_port": 1})
    assert r.status_code == 201
    assert r.json()["port_count"] is None
    assert r.json()["uplink_port"] is None
```

- [ ] **Step 7: 运行全量设备 API 测试确认通过**

Run: `python -m pytest tests/test_devices_api.py -q`（backend 目录）
Expected: 全部通过。

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas.py backend/app/services/device_service.py backend/tests/test_devices_api.py
git commit -m "feat: switch port attributes schema, validation, and serialization"
```

---

### Task 3: 备份导出/导入含端口字段

**Files:**
- Modify: `backend/app/services/backup_service.py`
- Test: `backend/tests/test_backup_api.py`

**Interfaces:**
- Consumes: `Device.port_count`/`uplink_port`/`port_bindings`（Task 1 产出）。
- Produces: 备份 `weaver.json` 的 devices 条目含三字段；导入恢复。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_backup_api.py` 的 `_tree` 中，给 `sw1` 创建加端口字段：

```python
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1",
                      "parent_id": g["id"], "port_count": 8, "uplink_port": 1})
```

追加：

```python
def test_export_includes_port_fields(client, admin_headers):
    _tree(client, admin_headers)
    data = _export_json(client, admin_headers)
    sw1 = next(d for d in data["devices"] if d["name"] == "sw1")
    assert sw1["port_count"] == 8
    assert sw1["uplink_port"] == 1


def test_import_restores_port_fields(client, admin_headers):
    _tree(client, admin_headers)
    data = _export_json(client, admin_headers)
    r = client.post("/api/backup/import", headers=admin_headers,
                    json={"mode": "replace"}, content=json.dumps(data).encode())
    assert r.status_code == 200
    got = client.get("/api/devices", headers=admin_headers).json()
    sw1 = next(d for d in got if d["name"] == "sw1")
    assert sw1["port_count"] == 8
    assert sw1["uplink_port"] == 1


def test_import_old_backup_without_ports(client, admin_headers):
    data = {"version": 2, "devices": [{"id": 1, "name": "old", "type": "switch"}]}
    r = client.post("/api/backup/import", headers=admin_headers,
                    json={"mode": "replace"}, content=json.dumps(data).encode())
    assert r.status_code == 200
    got = client.get("/api/devices", headers=admin_headers).json()
    assert got[0]["name"] == "old"
    assert got[0]["port_count"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_backup_api.py -k "port_fields or old_backup" -q`（backend 目录）
Expected: FAIL（导出无 port_count）。

- [ ] **Step 3: 导出加字段**

`backend/app/services/backup_service.py` `_flatten_devices` 的 `item` dict 追加：

```python
            "port_count": d.port_count,
            "uplink_port": d.uplink_port,
            "port_bindings": d.port_bindings,
```

- [ ] **Step 4: 导入加字段**

`_import_devices` 的 `Device(...)` 构造追加：

```python
            port_count=item.get("port_count"),
            uplink_port=item.get("uplink_port"),
            port_bindings=item.get("port_bindings"),
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_backup_api.py -q`（backend 目录）
Expected: 全部通过。

- [ ] **Step 6: 全量后端回归**

Run: `python -m pytest -q`（backend 目录）
Expected: 全部通过（原 132 + 新增）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/backup_service.py backend/tests/test_backup_api.py
git commit -m "feat: include switch port fields in backup export and import"
```

---

### Task 4: 前端类型 + PortBindingDialog + MainView 集成

**Files:**
- Modify: `frontend/src/utils/deviceTypes.js`
- Create: `frontend/src/components/PortBindingDialog.vue`
- Modify: `frontend/src/views/MainView.vue`
- Test: `frontend/src/utils/__tests__/deviceTypes.spec.js`
- Create: `frontend/src/components/__tests__/PortBindingDialog.spec.js`
- Modify: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: `deviceForm.type`、`deviceForm.port_count`/`uplink_port`/`port_bindings`、`deviceCandidates`（MainView 现有）。
- Produces: `PortBindingDialog` props `{ modelValue, portCount, bindings, childDevices }`，emits `update:modelValue`、`save(bindings)`；`DEVICE_TYPE_LABELS.unmanaged_switch`、`DEVICE_TYPE_ICONS.unmanaged_switch`。

- [ ] **Step 1: 写失败测试（deviceTypes）**

`frontend/src/utils/__tests__/deviceTypes.spec.js` 顶部 import 追加 `DEVICE_TYPE_LABELS`：

```js
import { DEVICE_TYPE_ICONS, DEVICE_TYPE_LABELS, allTypeOptions, typeIcon, typeLabel } from '../deviceTypes'
```

并在 describe 内追加：

```js
  it('unmanaged_switch 有标签与图标', () => {
    expect(DEVICE_TYPE_LABELS.unmanaged_switch).toBe('非管理型交换机')
    expect(DEVICE_TYPE_ICONS.unmanaged_switch).toBeTruthy()
  })
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/utils/__tests__/deviceTypes.spec.js`（frontend 目录）
Expected: FAIL（undefined）。

- [ ] **Step 3: deviceTypes 加 unmanaged_switch**

`frontend/src/utils/deviceTypes.js`：

```js
  unmanaged_switch: '非管理型交换机',
```

`DEVICE_TYPE_ICONS` 追加 `unmanaged_switch: 'Connection'`。

- [ ] **Step 4: 写 PortBindingDialog 测试**

创建 `frontend/src/components/__tests__/PortBindingDialog.spec.js`：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PortBindingDialog from '../PortBindingDialog.vue'

const childDevices = [
  { id: 101, name: '服务器A' },
  { id: 102, name: '摄像头B' },
]

describe('PortBindingDialog', () => {
  it('按端口总数渲染端口行', () => {
    const wrapper = mount(PortBindingDialog, {
      props: { modelValue: true, portCount: 4, bindings: {}, childDevices },
      global: { stubs: { ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' }, ElSelect: { template: '<div><slot /></div>' }, ElOption: { template: '<div><slot /></div>' }, ElButton: { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.findAll('.port-row').length).toBe(4)
  })

  it('保存时仅保留绑定了设备的端口', async () => {
    const wrapper = mount(PortBindingDialog, {
      props: { modelValue: true, portCount: 3, bindings: { 1: { target_id: 101, type: 'uplink' } }, childDevices },
      global: { stubs: { ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' }, ElSelect: { props: ['modelValue'], emits: ['update:modelValue'], template: '<div class="sel"><slot /></div>' }, ElOption: { template: '<div><slot /></div>' }, ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' } } },
    })
    await wrapper.findAll('button').find((b) => b.text() === '保存').trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')[0][0]).toEqual({ 1: { target_id: 101, type: 'uplink' } })
  })
})
```

- [ ] **Step 5: 运行确认失败**

Run: `npx vitest run src/components/__tests__/PortBindingDialog.spec.js`（frontend 目录）
Expected: FAIL（组件不存在）。

- [ ] **Step 6: 实现 PortBindingDialog**

创建 `frontend/src/components/PortBindingDialog.vue`：

```vue
<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  portCount: { type: Number, default: 0 },
  bindings: { type: Object, default: () => ({}) },
  childDevices: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'save'])

const rows = ref([])

watch(
  () => [props.portCount, props.modelValue],
  () => {
    if (!props.modelValue) return
    rows.value = Array.from({ length: props.portCount }, (_, i) => {
      const port = String(i + 1)
      const existing = props.bindings[port]
      return {
        port,
        target_id: existing ? existing.target_id : null,
        type: existing ? existing.type : 'downlink',
      }
    })
  },
  { immediate: true }
)

function onClose() {
  emit('update:modelValue', false)
}

function onSave() {
  const result = {}
  for (const row of rows.value) {
    if (row.target_id) {
      result[row.port] = { target_id: row.target_id, type: row.type }
    }
  }
  emit('save', result)
  onClose()
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="端口绑定配置" width="520px" @close="onClose">
    <div v-for="row in rows" :key="row.port" class="port-row">
      <span class="port-num">Port {{ row.port }}</span>
      <el-select v-model="row.target_id" placeholder="绑定设备" clearable class="bind-select">
        <el-option v-for="d in childDevices" :key="d.id" :label="d.name" :value="d.id" />
      </el-select>
      <el-select v-model="row.type" class="type-select">
        <el-option label="下联" value="downlink" />
        <el-option label="上联" value="uplink" />
      </el-select>
    </div>
    <template #footer>
      <el-button @click="onClose">取消</el-button>
      <el-button type="primary" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.port-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.port-num {
  width: 60px;
  color: #606266;
}
.bind-select {
  flex: 1;
}
.type-select {
  width: 100px;
}
</style>
```

- [ ] **Step 7: 运行 PortBindingDialog 测试确认通过**

Run: `npx vitest run src/components/__tests__/PortBindingDialog.spec.js`（frontend 目录）
Expected: PASS。

- [ ] **Step 8: 写 MainView 测试**

`frontend/src/views/__tests__/MainView.spec.js` 追加：

```js
describe('MainView 交换机端口字段', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('交换机类显示端口字段与配置按钮', async () => {
    authState.role = 'admin'
    updateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    wrapper.find('.view-switch').vm.$emit('update:modelValue', 'table')
    await flushPromises()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('端口总数')
    expect(wrapper.text()).toContain('上联端口')
    expect(wrapper.text()).toContain('配置端口绑定')
  })

  it('非交换机类不显示端口字段', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    wrapper.find('.view-switch').vm.$emit('update:modelValue', 'table')
    await flushPromises()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    // 编辑后手动把类型改成 group，端口字段应消失
    await wrapper.find('.t-input[value="核心交换机"]').setValue('核心交换机')
    wrapper.vm.deviceForm.type = 'group'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('端口总数')
    expect(wrapper.text()).not.toContain('配置端口绑定')
  })
})
```

注意：默认 `viewMode === 'tree'`，必须先切到 table 再点编辑。stub 的 `onEdit` 传入无 `children` 的设备（`portChildDevices` 为 `[]`，无碍此断言）。

- [ ] **Step 9: 运行确认失败**

Run: `npx vitest run src/views/__tests__/MainView.spec.js`（frontend 目录）
Expected: FAIL（无端口字段）。

- [ ] **Step 10: MainView 集成**

`MainView.vue`：
1. import 追加 `PortBindingDialog`。
2. `deviceForm` 初始追加 `port_count: null, uplink_port: null, port_bindings: {}`。
3. 新增 ref：`portDialogVisible = ref(false)`、`portChildDevices = ref([])`。
4. `openDeviceEdit` 中 `deviceForm.value = { ..., port_count: device.port_count ?? null, uplink_port: device.uplink_port ?? null, port_bindings: device.port_bindings ?? {} }`，并追加（直接子节点来自树的 children，`flattenTree` 保留 children）：

```js
  portChildDevices.value = (device.children || []).map((c) => ({ id: c.id, name: c.name }))
```

5. `onSaveDevice` 的 payload 追加 `port_count: deviceForm.value.port_count, uplink_port: deviceForm.value.uplink_port, port_bindings: Object.keys(deviceForm.value.port_bindings).length ? deviceForm.value.port_bindings : null`。
6. 新增函数：

```js
function openPortDialog() {
  portDialogVisible.value = true
}

function onPortBindingsSave(bindings) {
  deviceForm.value.port_bindings = bindings
}
```

7. 模板中设备编辑弹窗，在"位置" form-item 后追加：

```html
          <el-form-item v-if="deviceForm.type === 'switch' || deviceForm.type === 'unmanaged_switch'" label="端口总数">
            <el-input-number v-model="deviceForm.port_count" :min="1" :max="48" />
          </el-form-item>
          <el-form-item v-if="deviceForm.type === 'switch' || deviceForm.type === 'unmanaged_switch'" label="上联端口">
            <el-input-number v-model="deviceForm.uplink_port" :min="1" :max="48" />
          </el-form-item>
          <el-form-item v-if="deviceForm.type === 'switch' || deviceForm.type === 'unmanaged_switch'" label="端口绑定">
            <el-button size="small" @click="openPortDialog">配置端口绑定</el-button>
          </el-form-item>
```

8. 设备编辑弹窗 `</el-dialog>` 后追加 PortBindingDialog：

```html
      <PortBindingDialog
        v-model="portDialogVisible"
        :port-count="deviceForm.port_count || 0"
        :bindings="deviceForm.port_bindings"
        :child-devices="portChildDevices"
        @save="onPortBindingsSave"
      />
```

- [ ] **Step 11: 运行确认通过**

Run: `npx vitest run src/views/__tests__/MainView.spec.js src/components/__tests__/PortBindingDialog.spec.js src/utils/__tests__/deviceTypes.spec.js`（frontend 目录）
Expected: 全部通过。

- [ ] **Step 12: 全量前端回归 + 构建**

Run: `npm test`（frontend 目录），再 `npm run build`
Expected: 全测试通过，build 成功。

- [ ] **Step 13: 提交**

```bash
git add frontend/src/utils/deviceTypes.js frontend/src/components/PortBindingDialog.vue frontend/src/views/MainView.vue frontend/src/utils/__tests__/deviceTypes.spec.js frontend/src/components/__tests__/PortBindingDialog.spec.js frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: switch port attributes UI with port binding dialog"
```

---

### Task 5: 真实浏览器验证 + 版本发布

**Files:**
- Modify: `backend/app/main.py`、`frontend/package.json`（版本号 0.4.8 → 0.4.9）

**Interfaces:**
- Consumes: Task 1-4 全部产物。

- [ ] **Step 1: 启动 preview + playwright 验证**

启动 preview：`npx vite preview --port 4173 --strictPort`（后台）。
用 playwright-core + 系统 Edge 打开 `http://localhost:4173/`，登录 admin/admin123（`/api/**` 转发 `http://10.0.11.252:8000`），进入设备页表格，编辑一个 switch 设备验证：
- 端口总数/上联端口输入框出现。
- "配置端口绑定"按钮出现。
- 非交换机设备编辑时不显示端口字段。

预期：无 console error。

- [ ] **Step 2: 版本 bump 并发布**

用 Edit 工具将 `backend/app/main.py` 与 `frontend/package.json` 版本 `0.4.8` → `0.4.9`。

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.9"
git tag 0.4.9
git push origin main --tags
```

- [ ] **Step 3: CI 轮询**

REST API 查询 Actions runs（sha 匹配），轮询至 `status=completed`、`conclusion=success`。

- [ ] **Step 4: ghcr 确认**

`https://ghcr.io/token?scope=repository:langdalebecks204-bit/webweaver:pull` 取 token，`GET /v2/langdalebecks204-bit/webweaver/manifests/0.4.9` 返回 200 与 digest。

- [ ] **Step 5: 清理**

停 preview 进程，删除临时 playwright 脚本。