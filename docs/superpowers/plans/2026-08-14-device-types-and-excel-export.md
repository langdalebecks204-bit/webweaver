# 设备类型扩展与表格 CSV 导出 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩充设备类型（内置 12 类 + 自定义类型管理），并将设备资产表格导出为 CSV。

**Architecture:** 设备类型以常量 + settings 表 JSON 存储，后端提供内置/自定义类型查询与增删接口，创建/更新设备时做运行时类型校验；前端新增类型 API/store、中文映射与图标映射模块，设备表单下拉与树图标读取该模块；CSV 导出为纯前端生成（手写序列化函数，无新依赖）。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2；Vue 3 + Pinia + Element Plus（`@element-plus/icons-vue`）；vitest + @vue/test-utils；pytest。

## Global Constraints

- 不修改 `Device.type` 表结构（仍为 `String(20)`）。
- 内置类型集合固定为：`group, server, switch, terminal, camera, nvr, router, firewall, ap, printer, nas, ups`。
- 自定义类型名称规则：`^[a-zA-Z0-9_-]{1,20}$`，不与内置类型或已有自定义类型重复。
- 删除自定义类型时，事务内把引用该类型的设备 `type` 改为 `terminal`。
- 内置类型不可删除。
- 前端图标映射固定如下（全部经 `@element-plus/icons-vue` 验证存在）：
  group→Folder, server→Monitor, switch→Connection, terminal→Cpu, camera→VideoCamera, nvr→Film, router→Position, firewall→Lock, ap→Cellphone, printer→Printer, nas→Files, ups→Lightning；自定义→Monitor，未知→QuestionFilled。
- CSV 导出为纯前端，无新 npm 依赖；必须带 `\uFEFF` BOM。
- 中文映射：group→分组, server→服务器, switch→交换机, terminal→终端, camera→摄像头, nvr→NVR, router→路由器, firewall→防火墙, ap→无线AP, printer→打印机, nas→NAS, ups→UPS。
- 用户明确：本次为小版本升级（版本号 bump 到 0.4.0）。

---

### Task 1: 后端设备类型工具与服务

**Files:**
- Create: `backend/app/services/device_types.py`
- Modify: `backend/app/services/setting_service.py`（可选，见步骤）
- Test: `backend/tests/test_device_types.py`

**Interfaces:**
- Produces:
  - `BUILTIN_TYPES: list[str]`
  - `get_custom_types(db: Session) -> list[str]`
  - `set_custom_types(db: Session, names: list[str]) -> None`
  - `is_valid_type(db: Session, t: str) -> bool`
  - `CUSTOM_TYPES_KEY = "custom_device_types"`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_device_types.py
from app.database import SessionLocal
from app.models import Setting
from app.services import device_types as dt


def test_builtin_types_contains_new_ones():
    for t in ["camera", "nvr", "router", "firewall", "ap", "printer", "nas", "ups"]:
        assert t in dt.BUILTIN_TYPES


def test_custom_types_default_empty():
    with SessionLocal() as db:
        assert dt.get_custom_types(db) == []


def test_set_custom_types_persists():
    with SessionLocal() as db:
        dt.set_custom_types(db, ["printer2"])
        assert dt.get_custom_types(db) == ["printer2"]
        row = db.get(Setting, dt.CUSTOM_TYPES_KEY)
        assert row is not None
        assert "printer2" in row.value


def test_is_valid_type():
    with SessionLocal() as db:
        assert dt.is_valid_type(db, "group") is True
        assert dt.is_valid_type(db, "camera") is True
        assert dt.is_valid_type(db, "bogus") is False
        dt.set_custom_types(db, ["nas2"])
        assert dt.is_valid_type(db, "nas2") is True
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest backend/tests/test_device_types.py -v`
Expected: FAIL（`from app.services import device_types` ImportError）

- [ ] **Step 3: 实现 `device_types.py`**

```python
# backend/app/services/device_types.py
import json

from sqlalchemy.orm import Session

from app.models import Setting

BUILTIN_TYPES = [
    "group",
    "server",
    "switch",
    "terminal",
    "camera",
    "nvr",
    "router",
    "firewall",
    "ap",
    "printer",
    "nas",
    "ups",
]

CUSTOM_TYPES_KEY = "custom_device_types"


def get_custom_types(db: Session) -> list[str]:
    row = db.get(Setting, CUSTOM_TYPES_KEY)
    if row is None:
        return []
    try:
        value = json.loads(row.value)
    except (ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(x) for x in value]


def set_custom_types(db: Session, names: list[str]) -> None:
    row = db.get(Setting, CUSTOM_TYPES_KEY)
    if row is None:
        db.add(Setting(key=CUSTOM_TYPES_KEY, value=json.dumps(names)))
    else:
        row.value = json.dumps(names)
    db.commit()


def is_valid_type(db: Session, t: str) -> bool:
    return t in BUILTIN_TYPES or t in get_custom_types(db)
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest backend/tests/test_device_types.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/device_types.py backend/tests/test_device_types.py
git commit -m "feat: add device type constants and custom type storage"
```

---

### Task 2: 设备类型管理接口

**Files:**
- Create: `backend/app/routers/device_types.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_device_types_api.py`

**Interfaces:**
- Consumes: `app.services.device_types`（Task 1 的 `BUILTIN_TYPES`, `get_custom_types`, `set_custom_types`）
- Produces:
  - `GET /api/settings/device-types` → `{ "builtin": [...], "custom": [...] }`（任意登录用户）
  - `POST /api/settings/device-types` body `{"name": "..."}` → 201 `{ "ok": true, "custom": [...] }`（admin）
  - `DELETE /api/settings/device-types/{name}` → 200 `{ "ok": true }`（admin）
  - `TYPE_NAME_PATTERN = r"^[a-zA-Z0-9_-]{1,20}$"`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_device_types_api.py
from app.database import SessionLocal
from app.models import Device
from app.services import device_types as dt


def _mk_viewer(client):
    from app.models import User
    from app.security import hash_password

    with SessionLocal() as db:
        db.add(User(username="viewer_types", password_hash=hash_password("pass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer_types", "password": "pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_device_types(client, admin_headers):
    r = client.get("/api/settings/device-types", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "camera" in body["builtin"]
    assert body["custom"] == []


def test_add_custom_type(client, admin_headers):
    r = client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    assert r.status_code == 201
    assert "nas2" in r.json()["custom"]
    with SessionLocal() as db:
        assert "nas2" in dt.get_custom_types(db)


def test_add_custom_type_duplicates_and_invalid(client, admin_headers):
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "switch"}
    ).status_code == 409
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "nas2"}
    ).status_code == 201
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "nas2"}
    ).status_code == 409
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "a b"}
    ).status_code == 422
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": "x" * 21}
    ).status_code == 422
    assert client.post(
        "/api/settings/device-types", headers=admin_headers, json={"name": ""}
    ).status_code == 422


def test_delete_custom_type_reassigns_devices(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "NAS2节点", "type": "nas2", "ip_address": "10.1.1.1"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "nas2"

    r = client.delete("/api/settings/device-types/nas2", headers=admin_headers)
    assert r.status_code == 200
    with SessionLocal() as db:
        dev = db.query(Device).filter(Device.name == "NAS2节点").one()
        assert dev.type == "terminal"


def test_delete_builtin_rejected(client, admin_headers):
    r = client.delete("/api/settings/device-types/camera", headers=admin_headers)
    assert r.status_code in (400, 422)


def test_device_types_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.post(
        "/api/settings/device-types", headers=vh, json={"name": "nas2"}
    ).status_code == 403
    assert client.delete("/api/settings/device-types/nas2", headers=vh).status_code == 403
    # GET 允许任意登录用户
    assert client.get("/api/settings/device-types", headers=vh).status_code == 200
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest backend/tests/test_device_types_api.py -v`
Expected: FAIL（路由 404）

- [ ] **Step 3: 实现路由**

```python
# backend/app/routers/device_types.py
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Device, User
from app.services import device_types as dt

router = APIRouter()

TYPE_NAME_PATTERN = r"^[a-zA-Z0-9_-]{1,20}$"
_type_re = re.compile(TYPE_NAME_PATTERN)


class DeviceTypeCreate(BaseModel):
    name: str


@router.get("/device-types")
def list_device_types(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return {"builtin": dt.BUILTIN_TYPES, "custom": dt.get_custom_types(db)}


@router.post("/device-types", status_code=201)
def add_device_type(
    payload: DeviceTypeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = (payload.name or "").strip()
    if not _type_re.match(name):
        raise HTTPException(status_code=422, detail="类型名须为 1-20 位字母/数字/下划线/连字符")
    if name in dt.BUILTIN_TYPES:
        raise HTTPException(status_code=409, detail="内置类型不可重复添加")
    custom = dt.get_custom_types(db)
    if name in custom:
        raise HTTPException(status_code=409, detail="类型已存在")
    custom.append(name)
    dt.set_custom_types(db, custom)
    return {"ok": True, "custom": dt.get_custom_types(db)}


@router.delete("/device-types/{name}")
def remove_device_type(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if name in dt.BUILTIN_TYPES:
        raise HTTPException(status_code=400, detail="内置类型不可删除")
    custom = dt.get_custom_types(db)
    if name not in custom:
        raise HTTPException(status_code=404, detail="自定义类型不存在")
    custom = [x for x in custom if x != name]
    dt.set_custom_types(db, custom)
    db.execute(update(Device).where(Device.type == name).values(type="terminal"))
    db.commit()
    return {"ok": True}
```

修改 `backend/app/main.py`，在 imports 区加 `from app.routers import device_types`，在 include_router 区加：

```python
app.include_router(device_types.router, prefix="/api/settings", tags=["settings"])
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest backend/tests/test_device_types_api.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/device_types.py backend/app/main.py backend/tests/test_device_types_api.py
git commit -m "feat: add device type management API"
```

---

### Task 3: 设备创建/更新类型校验放宽

**Files:**
- Modify: `backend/app/schemas.py:27,40`
- Modify: `backend/app/services/device_service.py:63-113`
- Test: `backend/tests/test_device_types_api.py`（追加）

**Interfaces:**
- Consumes: `app.services.device_types.is_valid_type`
- Produces: 无新接口；`create_device`/`update_device` 在类型非法时抛 `ValueError("invalid device type: <t>")`，路由层转 409（沿用现有 catch）。

- [ ] **Step 1: 写失败测试（追加到 test_device_types_api.py）**

```python
def test_create_device_with_custom_type(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "NAS节点", "type": "nas2", "ip_address": "10.2.2.2"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "nas2"


def test_create_device_with_unknown_type_rejected(client, admin_headers):
    r = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "未知类型节点", "type": "bogus"},
    )
    assert r.status_code in (409, 422)
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest backend/tests/test_device_types_api.py -k custom_type -v`
Expected: FAIL（`bogus` 通过固定正则被 409 之外方式拒绝；`nas2` 被 422 pattern 拒绝）

- [ ] **Step 3: 修改 schemas.py**

`schemas.py` 中 `DeviceBase.type`（第 27 行）改为：

```python
    type: str = Field(default="group", min_length=1, max_length=20)
```

`DeviceUpdate.type`（第 40 行）改为：

```python
    type: str | None = Field(default=None, min_length=1, max_length=20)
```

- [ ] **Step 4: 修改 device_service.py**

在 `create_device` 函数开头（`if data.parent_id` 之前）加：

```python
    if not is_valid_type(db, data.type):
        raise ValueError(f"invalid device type: {data.type}")
```

在 `update_device` 函数中 `changes = data.model_dump(exclude_unset=True)` 之后加：

```python
    if "type" in changes and not is_valid_type(db, changes["type"]):
        raise ValueError(f"invalid device type: {changes['type']}")
```

文件顶部 import 加：

```python
from app.services.device_types import is_valid_type
```

注意：`update_device` 里 `changes` 可能在未设置 type 时不含该键；上面用 `"type" in changes` 判断。

- [ ] **Step 5: 运行验证通过**

Run: `python -m pytest backend/tests/test_device_types_api.py backend/tests/test_devices_api.py backend/tests/test_device_service.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas.py backend/app/services/device_service.py backend/tests/test_device_types_api.py
git commit -m "feat: runtime device type validation with custom types"
```

---

### Task 4: 备份导入兼容自定义类型

**Files:**
- Modify: `backend/app/services/backup_service.py:16,140-151,124-131`
- Test: `backend/tests/test_backup_api.py`（追加）

**Interfaces:**
- Consumes: `app.services.device_types.get_custom_types`
- Produces: 无新接口；`import_backup` 导入 devices 时接受「内置 + 备份/当前自定义」类型。

- [ ] **Step 1: 写失败测试（追加到 test_backup_api.py）**

先读现有 test_backup_api.py 的 export/import 辅助函数，沿用其模式：

```python
def test_import_backup_with_custom_type(client, admin_headers):
    client.post("/api/settings/device-types", headers=admin_headers, json={"name": "nas2"})
    payload = {
        "version": 2,
        "devices": [
            {
                "id": 1,
                "name": "NAS节点",
                "type": "nas2",
                "parent_id": None,
                "order_index": 0,
            }
        ],
    }
    import json as _json
    r = client.post(
        "/api/backup/import?mode=replace",
        headers=admin_headers,
        content=_json.dumps(payload),
    )
    assert r.status_code == 200
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest backend/tests/test_backup_api.py::test_import_backup_with_custom_type -v`
Expected: FAIL（422 invalid device type）

- [ ] **Step 3: 修改 backup_service.py**

`_VALID_TYPES`（第 16 行）改为：

```python
def _valid_types(db: Session) -> set[str]:
    from app.services.device_types import BUILTIN_TYPES, get_custom_types

    return set(BUILTIN_TYPES) | set(get_custom_types(db))
```

`_import_devices` 签名改为 `_import_devices(db, items, merge, images)` 保持（已有 db 参数），把其中：

```python
        if dev_type not in _VALID_TYPES:
            raise ValueError(f"invalid device type: {dev_type}")
```

改为：

```python
        if dev_type not in _valid_types(db):
            raise ValueError(f"invalid device type: {dev_type}")
```

注意 `_import_replace`（124-131 行）中先 `_import_devices` 后 `_import_settings`，若备份 settings 里含自定义类型，导入 devices 时可能还读不到——因此 `_valid_types(db)` 合并了「当前 DB 已有」的自定义类型，且在 replace 模式下 DB 的 settings 已被清空。为稳妥，`_import_replace` 应先把 settings 里的 custom_device_types 合并进 DB。修改 `_import_replace`：

```python
def _import_replace(db: Session, data: dict, images: dict[str, bytes]) -> None:
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    clear_all_images()
    _import_settings(db, data.get("settings", []))
    _import_devices(db, data.get("devices", []), merge=False, images=images)
    _import_external(db, data.get("external", []), merge=False)
```

（把 `_import_settings` 移到 `_import_devices` 之前，保证自定义类型先注册。）

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest backend/tests/test_backup_api.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/backup_service.py backend/tests/test_backup_api.py
git commit -m "feat: allow importing backups with custom device types"
```

---

### Task 5: 前端类型 API 与 store

**Files:**
- Modify: `frontend/src/api/settings.js`
- Modify: `frontend/src/stores/settings.js`
- Test: `frontend/src/stores/__tests__/settings.spec.js`（追加）

**Interfaces:**
- Consumes: 后端 `GET/POST/DELETE /api/settings/device-types`
- Produces:
  - `fetchDeviceTypes()`, `addDeviceType(name)`, `removeDeviceType(name)`
  - settings store state: `builtinTypes: []`, `customTypes: []`, `typesLoaded: false`
  - settings store actions: `loadTypes()`, `addType(name)`, `removeType(name)`

- [ ] **Step 1: 写失败测试（追加到 settings.spec.js）**

先读现有 `frontend/src/stores/__tests__/settings.spec.js` 的 mock 方式，沿用：

```javascript
// 在文件顶部 vi.hoisted 增加 mock 后追加 describe
import { fetchDeviceTypes, addDeviceType, removeDeviceType } from '../../api/settings'
// 追加测试：
describe('settings 设备类型', () => {
  it('loadTypes 拉取内置与自定义类型', async () => {
    fetchDeviceTypes.mockResolvedValue({ data: { builtin: ['group', 'camera'], custom: ['nas2'] } })
    const store = useSettingsStore()
    await store.loadTypes()
    expect(store.builtinTypes).toEqual(['group', 'camera'])
    expect(store.customTypes).toEqual(['nas2'])
    expect(store.typesLoaded).toBe(true)
  })

  it('addType 调用接口并刷新列表', async () => {
    addDeviceType.mockResolvedValue({ data: { ok: true } })
    fetchDeviceTypes.mockResolvedValue({ data: { builtin: ['group'], custom: ['nas2'] } })
    const store = useSettingsStore()
    await store.addType('nas2')
    expect(addDeviceType).toHaveBeenCalledWith('nas2')
    expect(store.customTypes).toContain('nas2')
  })

  it('removeType 调用接口并从列表移除', async () => {
    removeDeviceType.mockResolvedValue({ data: { ok: true } })
    fetchDeviceTypes.mockResolvedValue({ data: { builtin: ['group'], custom: [] } })
    const store = useSettingsStore()
    store.customTypes = ['nas2']
    await store.removeType('nas2')
    expect(removeDeviceType).toHaveBeenCalledWith('nas2')
    expect(store.customTypes).toEqual([])
  })
})
```

- [ ] **Step 2: 运行验证失败**

Run: `npm run test -- --run src/stores/__tests__/settings.spec.js`
Expected: FAIL（`fetchDeviceTypes` 未定义等）

- [ ] **Step 3: 实现 api/settings.js**

追加：

```javascript
export function fetchDeviceTypes() {
  return client.get('/settings/device-types')
}

export function addDeviceType(name) {
  return client.post('/settings/device-types', { name })
}

export function removeDeviceType(name) {
  return client.delete(`/settings/device-types/${encodeURIComponent(name)}`)
}
```

- [ ] **Step 4: 实现 stores/settings.js**

```javascript
import { defineStore } from 'pinia'
import {
  addDeviceType,
  fetchDeviceTypes,
  fetchInspectionInterval,
  removeDeviceType,
  updateInspectionInterval,
} from '../api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    pollIntervalMinutes: 5,
    loading: false,
    builtinTypes: [],
    customTypes: [],
    typesLoaded: false,
  }),
  actions: {
    async loadInterval() {
      this.loading = true
      try {
        const { data } = await fetchInspectionInterval()
        this.pollIntervalMinutes = data.poll_interval_minutes
      } finally {
        this.loading = false
      }
    },
    async saveInterval(minutes) {
      const { data } = await updateInspectionInterval(minutes)
      this.pollIntervalMinutes = data.poll_interval_minutes
    },
    async loadTypes() {
      const { data } = await fetchDeviceTypes()
      this.builtinTypes = data.builtin
      this.customTypes = data.custom
      this.typesLoaded = true
    },
    async addType(name) {
      await addDeviceType(name)
      await this.loadTypes()
    },
    async removeType(name) {
      await removeDeviceType(name)
      await this.loadTypes()
    },
  },
})
```

- [ ] **Step 5: 运行验证通过**

Run: `npm run test -- --run src/stores/__tests__/settings.spec.js`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/settings.js frontend/src/stores/settings.js frontend/src/stores/__tests__/settings.spec.js
git commit -m "feat: add device types API and settings store"
```

---

### Task 6: 前端类型中文映射与图标映射模块

**Files:**
- Create: `frontend/src/utils/deviceTypes.js`
- Test: `frontend/src/utils/__tests__/deviceTypes.spec.js`

**Interfaces:**
- Produces:
  - `DEVICE_TYPE_LABELS: Record<string, string>`（内置中文名）
  - `DEVICE_TYPE_ICONS: Record<string, string>`（Element 图标组件名，字符串）
  - `DEFAULT_TYPE_ICON = "Monitor"`
  - `typeLabel(type: string) -> string`（未知返回原值）
  - `typeIcon(type: string) -> string`（未知/自定义返回默认）
  - `allTypeOptions(builtin, custom) -> [{ value, label }]`（下拉选项，内置中文 + 自定义原值）

- [ ] **Step 1: 写失败测试**

```javascript
// frontend/src/utils/__tests__/deviceTypes.spec.js
import { describe, it, expect } from 'vitest'
import { DEVICE_TYPE_ICONS, allTypeOptions, typeIcon, typeLabel } from '../deviceTypes'

describe('deviceTypes', () => {
  it('内置类型有中文标签', () => {
    expect(typeLabel('camera')).toBe('摄像头')
    expect(typeLabel('nvr')).toBe('NVR')
    expect(typeLabel('group')).toBe('分组')
  })

  it('未知类型原样返回', () => {
    expect(typeLabel('bogus')).toBe('bogus')
  })

  it('内置类型有专属图标，自定义走默认', () => {
    expect(DEVICE_TYPE_ICONS.camera).toBe('VideoCamera')
    expect(typeIcon('nas2')).toBe('Monitor')
    expect(typeIcon('bogus')).toBe('QuestionFilled')
  })

  it('allTypeOptions 合并内置中文与自定义原值', () => {
    const opts = allTypeOptions(['group', 'camera'], ['nas2'])
    expect(opts).toEqual([
      { value: 'group', label: '分组' },
      { value: 'camera', label: '摄像头' },
      { value: 'nas2', label: 'nas2' },
    ])
  })
})
```

- [ ] **Step 2: 运行验证失败**

Run: `npm run test -- --run src/utils/__tests__/deviceTypes.spec.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 deviceTypes.js**

```javascript
export const DEVICE_TYPE_LABELS = {
  group: '分组',
  server: '服务器',
  switch: '交换机',
  terminal: '终端',
  camera: '摄像头',
  nvr: 'NVR',
  router: '路由器',
  firewall: '防火墙',
  ap: '无线AP',
  printer: '打印机',
  nas: 'NAS',
  ups: 'UPS',
}

export const DEVICE_TYPE_ICONS = {
  group: 'Folder',
  server: 'Monitor',
  switch: 'Connection',
  terminal: 'Cpu',
  camera: 'VideoCamera',
  nvr: 'Film',
  router: 'Position',
  firewall: 'Lock',
  ap: 'Cellphone',
  printer: 'Printer',
  nas: 'Files',
  ups: 'Lightning',
}

export const DEFAULT_TYPE_ICON = 'Monitor'
export const UNKNOWN_TYPE_ICON = 'QuestionFilled'

export function typeLabel(type) {
  return DEVICE_TYPE_LABELS[type] || type
}

export function typeIcon(type) {
  if (!type) return UNKNOWN_TYPE_ICON
  return DEVICE_TYPE_ICONS[type] || DEFAULT_TYPE_ICON
}

export function allTypeOptions(builtinTypes, customTypes) {
  const opts = builtinTypes.map((t) => ({ value: t, label: DEVICE_TYPE_LABELS[t] || t }))
  for (const t of customTypes) {
    if (!DEVICE_TYPE_LABELS[t]) opts.push({ value: t, label: t })
  }
  return opts
}
```

- [ ] **Step 4: 运行验证通过**

Run: `npm run test -- --run src/utils/__tests__/deviceTypes.spec.js`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/deviceTypes.js frontend/src/utils/__tests__/deviceTypes.spec.js
git commit -m "feat: add device type label and icon mapping"
```

---

### Task 7: 前端设备类型 UI 集成

**Files:**
- Modify: `frontend/src/components/DeviceTree.vue:115-120,146-152`
- Modify: `frontend/src/views/MainView.vue:31,349-355,41-43`
- Modify: `frontend/src/components/DeviceTable.vue:78-80`
- Modify: `frontend/src/components/DeviceDetail.vue:136`
- Test: `frontend/src/components/__tests__/DeviceTree.spec.js`、`frontend/src/views/__tests__/MainView.spec.js`（追加）

**Interfaces:**
- Consumes: `useSettingsStore().loadTypes/builtinTypes/customTypes/typesLoaded`；`utils/deviceTypes` 的 `typeLabel/typeIcon/allTypeOptions`
- Produces: 无新接口；设备新建/编辑下拉显示全部类型，树图标按类型显示，表格/详情显示中文类型。

- [ ] **Step 1: 写失败测试（DeviceTree.spec.js 追加）**

在 DeviceTree.spec.js 的 `vi.mock` 区加 settings store mock：

```javascript
vi.mock('../../stores/settings', () => ({
  useSettingsStore: () => ({
    builtinTypes: ['group', 'server', 'switch', 'terminal', 'camera', 'nvr', 'router', 'firewall', 'ap', 'printer', 'nas', 'ups'],
    customTypes: ['nas2'],
    loadTypes: vi.fn(),
  }),
}))
```

追加测试：

```javascript
describe('DeviceTree 类型下拉与图标', () => {
  it('下拉包含新增的摄像头与自定义类型', async () => {
    const wrapper = mountTree('add-child')
    await flushPromises()
    const options = wrapper.findAll('.el-select-dropdown__item')
    const labels = options.map((o) => o.text())
    expect(labels).toContain('摄像头')
    expect(labels).toContain('nas2')
  })
})
```

注意：真实 `el-select` 下拉选项在 happy-dom 下渲染可能受限。若实测拿不到 `.el-select-dropdown__item`，改为断言组件内存在对应 `el-option`（`wrapper.findAll('option')` 或检查 `el-option` 组件）：

```javascript
    const options = wrapper.findAllComponents({ name: 'ElOption' })
    const values = options.map((o) => o.props('value'))
    expect(values).toContain('camera')
    expect(values).toContain('nas2')
```

- [ ] **Step 2: 运行验证失败**

Run: `npm run test -- --run src/components/__tests__/DeviceTree.spec.js`
Expected: FAIL（类型列表仍为写死的 4 项）

- [ ] **Step 3: 修改 DeviceTree.vue**

script 区顶部 import 加：

```javascript
import { useSettingsStore } from '../stores/settings'
import { allTypeOptions, typeIcon } from '../utils/deviceTypes'
```

在 `const store = useDevicesStore()` 后加：

```javascript
const settingsStore = useSettingsStore()
```

在 `parentCandidates` computed 后加：

```javascript
const typeOptions = computed(() =>
  allTypeOptions(settingsStore.builtinTypes, settingsStore.customTypes)
)
```

`onMounted` 时若未加载则加载：

```javascript
import { computed, onMounted, ref } from 'vue'
// ...
onMounted(() => {
  if (!settingsStore.typesLoaded) settingsStore.loadTypes()
})
```

模板类型下拉（146-152 行）改为：

```html
        <el-select v-model="form.type" style="width: 100%">
          <el-option
            v-for="opt in typeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
```

图标（115-120 行）改为：

```html
      <el-icon class="type-icon">
        <component :is="typeIcon(props.node.type)" />
      </el-icon>
```

- [ ] **Step 4: 修改 MainView.vue**

script 顶部 import 加 `allTypeOptions, typeLabel`：

```javascript
import { allTypeOptions, typeLabel } from '../utils/deviceTypes'
```

在 `onMounted` 中（settings.loadInterval 后）加：

```javascript
  await settings.loadTypes()
```

设备编辑对话框类型下拉（349-355 行）改为：

```html
            <el-select v-model="deviceForm.type" style="width: 100%">
              <el-option
                v-for="opt in typeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
```

`typeOptions` computed 加在 `isAdmin` 附近：

```javascript
const typeOptions = computed(() =>
  allTypeOptions(settings.builtinTypes, settings.customTypes)
)
```

（MainView 的编辑对话框由表格行编辑进入，`onSaveDevice` 用 store.update。）

- [ ] **Step 5: 修改 DeviceTable.vue 类型列**

第 78-80 行改为：

```html
      <el-table-column prop="type" label="类型" width="80">
        <template #default="{ row }">{{ typeLabel(row.type) }}</template>
      </el-table-column>
```

script 顶部加 `import { typeLabel } from '../utils/deviceTypes'`。

- [ ] **Step 6: 修改 DeviceDetail.vue 类型行**

第 136 行改为：

```html
          <li><span class="k">类型</span>{{ typeLabel(props.device.type) }}</li>
```

script 加 `import { typeLabel } from '../utils/deviceTypes'`（需确认该组件 script 区；若已是 `<script setup>` 直接在顶部加）。

- [ ] **Step 7: 运行验证通过**

Run: `npm run test -- --run src/components/__tests__/DeviceTree.spec.js src/views/__tests__/MainView.spec.js src/components/__tests__/DeviceTable.spec.js src/components/__tests__/DeviceDetail.spec.js`
Expected: PASS

注意：MainView.spec.js 现有 mock 需为 settings store 补 `builtinTypes/customTypes/loadTypes`（见 Task 5 的 mock 结构），否则 `computed` 读取 undefined 出错。`loadTypes` mock 用 `loadIntervalMock` 同款 `loadTypesMock`。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/components/DeviceTree.vue frontend/src/views/MainView.vue frontend/src/components/DeviceTable.vue frontend/src/components/DeviceDetail.vue frontend/src/components/__tests__/DeviceTree.spec.js frontend/src/views/__tests__/MainView.spec.js frontend/src/components/__tests__/DeviceTable.spec.js frontend/src/components/__tests__/DeviceDetail.spec.js
git commit -m "feat: integrate device types into tree, forms, table and detail"
```

---

### Task 8: 设置面板设备类型管理 UI

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Test: `frontend/src/views/__tests__/MainView.spec.js`（追加）

**Interfaces:**
- Consumes: settings store 的 `customTypes/builtinTypes/addType/removeType`
- Produces: 无新接口；admin 在设备页签工具栏下看到「类型管理」区域。

- [ ] **Step 1: 写失败测试（MainView.spec.js 追加）**

先读现有 `mountView` 的 stub 结构，追加 `el-input` 已 stub。新增测试：

```javascript
describe('MainView 设备类型管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示类型管理，添加自定义类型', async () => {
    authState.role = 'admin'
    addTypeMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('设备类型')
    const addInput = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型'))
    await addInput.setValue('nas2')
    const addBtn = wrapper.findAll('button').find((b) => b.text() === '添加')
    await addBtn.trigger('click')
    await flushPromises()
    expect(addTypeMock).toHaveBeenCalledWith('nas2')
  })

  it('删除自定义类型需确认', async () => {
    authState.role = 'admin'
    removeTypeMock.mockResolvedValue()
    confirmMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    const delBtn = wrapper.findAll('button').find((b) => b.text() === '删除类型')
    if (delBtn) {
      await delBtn.trigger('click')
      await flushPromises()
      expect(removeTypeMock).toHaveBeenCalled()
    }
  })

  it('viewer 不显示类型管理', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('设备类型')
  })
})
```

- [ ] **Step 2: 运行验证失败**

Run: `npm run test -- --run src/views/__tests__/MainView.spec.js`
Expected: FAIL（无「设备类型」文本；需补 mock）

- [ ] **Step 3: 更新 MainView.spec.js 的 settings store mock**

在现有 `vi.mock('../../stores/settings', ...)` 返回对象中补充：

```javascript
    builtinTypes: ['group', 'server', 'switch', 'terminal', 'camera', 'nvr', 'router', 'firewall', 'ap', 'printer', 'nas', 'ups'],
    customTypes: ['nas2'],
    loadTypes: vi.fn(),
    addType: addTypeMock,
    removeType: removeTypeMock,
```

（`addTypeMock/removeTypeMock` 需加入 vi.hoisted 定义，仿照现有 mock。）

- [ ] **Step 4: 实现类型管理 UI（MainView.vue 设备页签工具栏）**

在设备页签 card 的 `<template #header>` 内（stats div 之后）加：

```html
                <div v-if="isAdmin" class="type-manage">
                  <span>设备类型：</span>
                  <el-tag
                    v-for="t in settings.builtinTypes"
                    :key="t"
                    size="small"
                    class="type-tag"
                  >
                    {{ typeLabel(t) }}（内置）
                  </el-tag>
                  <el-tag
                    v-for="t in settings.customTypes"
                    :key="t"
                    size="small"
                    closable
                    @close="onRemoveCustomType(t)"
                    class="type-tag"
                  >
                    {{ t }}
                  </el-tag>
                  <el-input
                    v-model="newTypeName"
                    placeholder="自定义类型名"
                    size="small"
                    class="type-input"
                  />
                  <el-button size="small" type="primary" @click="onAddCustomType">添加</el-button>
                </div>
```

script 区加：

```javascript
const newTypeName = ref('')

async function onAddCustomType() {
  const name = (newTypeName.value || '').trim()
  if (!name) return
  try {
    await settings.addType(name)
    newTypeName.value = ''
    ElMessage.success('已添加')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  }
}

async function onRemoveCustomType(name) {
  try {
    await ElMessageBox.confirm(`删除类型"${name}"后，该类型下的设备将改为"终端"，继续？`, '删除类型', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await settings.removeType(name)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}
```

`typeLabel` 已在 Task 7 导入，MainView 顶部确认已 `import { typeLabel } from '../utils/deviceTypes'`。新增样式（在 style 区）：

```css
.type-manage { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.type-tag { margin-right: 4px; }
.type-input { width: 140px; }
```

- [ ] **Step 5: 运行验证通过**

Run: `npm run test -- --run src/views/__tests__/MainView.spec.js`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: add device type management UI in settings toolbar"
```

---

### Task 9: CSV 导出

**Files:**
- Create: `frontend/src/utils/csv.js`
- Modify: `frontend/src/components/DeviceTable.vue`
- Test: `frontend/src/utils/__tests__/csv.spec.js`、`frontend/src/components/__tests__/DeviceTable.spec.js`

**Interfaces:**
- Produces:
  - `toCsv(rows: Array<Record<string, any>>, columns: Array<{ key: string; header: string; format?: (v) => string }>) -> string`（带 BOM）
  - `escapeCsvField(value) -> string`
  - `downloadCsv(filename, content)`（Blob + a[download]，happy-dom 下可 mock）

- [ ] **Step 1: 写失败测试（csv.spec.js）**

```javascript
// frontend/src/utils/__tests__/csv.spec.js
import { describe, it, expect, vi } from 'vitest'
import { downloadCsv, escapeCsvField, toCsv } from '../csv'

describe('toCsv', () => {
  it('输出带 BOM 的 CSV', () => {
    const out = toCsv(
      [{ name: 'A', ip: '1.1.1.1' }],
      [
        { key: 'name', header: '名称' },
        { key: 'ip', header: 'IP' },
      ]
    )
    expect(out.charCodeAt(0)).toBe(0xfeff)
    expect(out).toContain('名称,IP')
    expect(out).toContain('A,1.1.1.1')
  })

  it('逗号引号换行转义', () => {
    const out = toCsv(
      [{ v: 'a,b"c\nd' }],
      [{ key: 'v', header: 'V' }]
    )
    expect(out).toContain('"a,b""c')
  })

  it('空值填空白', () => {
    const out = toCsv([{ a: null, b: undefined }], [{ key: 'a', header: 'A' }, { key: 'b', header: 'B' }])
    expect(out).toContain(',')
  })
})

describe('escapeCsvField', () => {
  it('无特殊字符原样返回', () => {
    expect(escapeCsvField('abc')).toBe('abc')
  })
  it('含逗号加引号', () => {
    expect(escapeCsvField('a,b')).toBe('"a,b"')
  })
  it('含引号加倍', () => {
    expect(escapeCsvField('a"b')).toBe('"a""b"')
  })
})

describe('downloadCsv', () => {
  it('创建 Blob 并触发下载', () => {
    const create = vi.fn(() => ({ url: 'blob:x' }))
    const revoke = vi.fn()
    const click = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    const anchor = { click, setAttribute: vi.fn(), style: {} }
    vi.stubGlobal('document', {
      createElement: () => anchor,
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    })
    downloadCsv('a.csv', 'x')
    expect(create).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
```

- [ ] **Step 2: 运行验证失败**

Run: `npm run test -- --run src/utils/__tests__/csv.spec.js`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 csv.js**

```javascript
export function escapeCsvField(value) {
  if (value === null || value === undefined) return ''
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function toCsv(rows, columns) {
  const header = columns.map((c) => escapeCsvField(c.header)).join(',')
  const lines = rows.map((row) =>
    columns.map((c) => escapeCsvField(c.format ? c.format(row[c.key]) : row[c.key])).join(',')
  )
  return '\uFEFF' + [header, ...lines].join('\r\n')
}

export function downloadCsv(filename, content) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 4: 实现 DeviceTable.vue 导出按钮**

script 加：

```javascript
import { downloadCsv, toCsv } from '../utils/csv'
import { typeLabel } from '../utils/deviceTypes'
```

模板 filters div 内（status select 后）加导出按钮：

```html
      <el-button size="small" @click="onExport">导出 CSV</el-button>
```

script 加函数：

```javascript
const statusLabel = (s) =>
  s === 'online' ? '在线' : s === 'offline' ? '离线' : s === 'warning' ? '警告' : '未知'

const csvColumns = [
  { key: 'name', header: '名称' },
  { key: 'type', header: '类型', format: typeLabel },
  { key: 'parentName', header: '所属分组', format: (v) => v || '' },
  { key: 'ip_address', header: 'IP', format: (v) => v || '' },
  { key: 'port', header: '端口', format: (v) => (v ?? '') },
  { key: 'location', header: '位置', format: (v) => v || '' },
  { key: 'status', header: '状态', format: statusLabel },
  { key: 'latency_ms', header: '延时', format: (v) => (v != null ? `${v} ms` : '') },
  { key: 'last_check', header: '最近巡检', format: (v) => (v ? new Date(v).toLocaleString() : '') },
]

function onExport() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('无数据可导出')
    return
  }
  downloadCsv(`设备资产_${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows, csvColumns))
  ElMessage.success(`已导出 ${rows.length} 条记录`)
}
```

注意 DeviceTable.vue 现有 statusText 函数与 `statusLabel` 重复；直接复用现有 `statusText`：

```javascript
function onExport() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('无数据可导出')
    return
  }
  const csv = toCsv(rows, csvColumns)
  downloadCsv(`设备资产_${new Date().toISOString().slice(0, 10)}.csv`, csv)
  ElMessage.success(`已导出 ${rows.length} 条记录`)
}
```

`csvColumns` 中 status format 用 `statusText`（现有函数）。

- [ ] **Step 5: 写 DeviceTable.spec.js 导出测试**

```javascript
describe('DeviceTable 导出 CSV', () => {
  it('点击导出生成带名称的下载', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 CSV')
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await flushPromises()
    expect(successMock).toHaveBeenCalledWith(expect.stringContaining('已导出'))
  })
})
```

（若 CSV 依赖 `URL.createObjectURL`/`document.createElement`，在 happy-dom 下可直接工作，无需 stub。若报错则在测试开头 mock。）

- [ ] **Step 6: 运行验证通过**

Run: `npm run test -- --run src/utils/__tests__/csv.spec.js src/components/__tests__/DeviceTable.spec.js`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/utils/csv.js frontend/src/components/DeviceTable.vue frontend/src/utils/__tests__/csv.spec.js frontend/src/components/__tests__/DeviceTable.spec.js
git commit -m "feat: export device table to CSV from frontend"
```

---

### Task 10: 全量回归 + 版本号升级

**Files:**
- Modify: `backend/app/main.py:29`（version）
- Modify: `frontend/package.json:5`（version）
- 不新增测试文件

**Interfaces:**
- Consumes: 全部前述任务
- Produces: 版本号 0.4.0

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && python -m pytest -q`
Expected: 全部通过（原 109 + 新增测试）

- [ ] **Step 2: 前端全量测试 + 构建**

Run: `cd frontend && npm run test && npm run build`
Expected: 全部通过，`dist/` 构建成功

- [ ] **Step 3: 手动验收清单**

- 登录 → 设备页签 → 表格 → 筛选 → 导出 CSV → Excel 打开中文正常。
- 树节点图标：切换 device type 后显示对应图标（camera→VideoCamera 等）。
- 新建/编辑设备下拉包含摄像头/NVR/自定义类型。
- 类型管理：添加 `nas2` → 设备下拉出现；删除 `nas2` → 引用设备变终端；内置类型无删除按钮。
- 详情页类型显示中文。
- 表格类型列显示中文。

- [ ] **Step 4: 更新版本号**

`backend/app/main.py:29`：

```python
app = FastAPI(title="织网 WebWeaver", version="0.4.0", lifespan=lifespan)
```

`frontend/package.json:5`：

```json
  "version": "0.4.0",
```

- [ ] **Step 5: 提交并打 tag**

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.0"
git tag 0.4.0
git push origin main
git push origin 0.4.0
```

（推送触发 CI 自动构建镜像并发布 ghcr。）

---

## 计划自审

- **Spec 覆盖**：节 1（类型体系）→ Task 1-4；节 2（图标）→ Task 6-7；节 3（CSV）→ Task 9；节 4（设置面板）→ Task 8；节 5（测试/验收）→ Task 10 手动清单。全部覆盖。
- **占位符**：无 TBD/TODO；每个步骤含实际代码与命令。
- **类型一致性**：`is_valid_type`/`get_custom_types`/`set_custom_types` 在各 Task 间签名一致；前端 `typeLabel/typeIcon/allTypeOptions` 签名一致；`loadTypes/addType/removeType` 一致。
- **潜在注意**：MainView.spec.js 现有 settings mock 需补 `loadTypes`（Task 7 提到）；`_import_replace` 顺序调整（Task 4）已有明确步骤；DeviceTree 下拉测试依赖 el-select 渲染，Task 7 步骤 1 给了降级断言方案。