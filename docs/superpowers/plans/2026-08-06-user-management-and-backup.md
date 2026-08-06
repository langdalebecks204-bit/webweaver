# 用户管理 + 数据备份导入导出 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供管理员用户管理界面（后端 `/api/users` 已存在，补齐前端），以及设备/外网目标/巡检间隔的备份导出、导入（替换/合并可选）与「清除所有数据（初始化）」。

**Architecture:** 后端新增 `backup_service.py`（序列化/反序列化/重置逻辑）+ `routers/backup.py`（`/api/backup/export|import|reset`，admin-only）。导入/重置用单事务；导入 body 为原生 JSON（未安装 python-multipart，不用 UploadFile）。前端新增 `api/users.js`、`stores/users.js`、`api/backup.js` 与组件 `UsersPanel.vue`、`BackupPanel.vue`；MainView 的 `el-tabs` 增「用户管理」「备份与恢复」两个 admin-only 页签。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic（后端）；Vue 3 + Pinia + Element Plus + Vitest（前端）。

## Global Constraints

- 工作区：直接在主仓 `D:\code\WebWeaver`，分支 `main`。
- 后端测试（workdir=backend）：`.venv\Scripts\python.exe -m pytest tests`，当前 67 passed。前端（workdir=frontend）：`npm run test`，当前 23 passed；构建 `npm run build`。
- 权限：备份三接口（export/import/reset）与用户管理均 **admin-only**（`require_admin`，viewer → 403）。前端对 viewer 隐藏「用户管理」「备份与恢复」页签。
- 备份 JSON `version == 1`；导入/重置单事务，校验失败整体回滚。
- 合并规则：设备**同名且同父则跳过**（不覆盖）；外网目标**同名跳过**；设置按备份值覆盖（upsert）。
- 导出不含用户账号与实时运行态（status/last_check 等）。
- 未安装 python-multipart → 导入用原始 JSON body（`await request.json()`），禁止用 UploadFile。
- 无代码注释（除非必需）。提交信息以 `feat:`/`test:`/`fix:`/`docs:` 前缀开头。
- 前端组件测试文件首行 `// @vitest-environment happy-dom`；store 纯逻辑测试用 node 环境（不写该行）。
- 现有后端 fixture：`conftest.py` 的 `clean_db` 已清 `Device/ExternalTarget/Setting/User`。

---

### Task 1: 后端备份导出（service + endpoint + 测试）

**Files:**
- Create: `backend/app/services/backup_service.py`
- Create: `backend/app/routers/backup.py`
- Modify: `backend/app/main.py:7,29`（注册 router）
- Create: `backend/tests/test_backup_api.py`

**Interfaces:**
- Consumes: `app.models.Device/ExternalTarget/Setting/utcnow`、`app.database.get_db`、`app.deps.require_admin`。
- Produces: `export_backup(db, include_devices: bool = True, include_external: bool = True, include_settings: bool = True) -> dict`（返回 `{"version": 1, "exported_at": str, "devices": [...], "external": [...], "settings": [...]}`，未选类别省略；devices 为「父在前、子在后」顺序）。Task 2/3 复用同一文件。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_backup_api.py`：

```python
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _tree(client, admin_headers):
    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"}).json()
    g = client.post("/api/devices", headers=admin_headers,
                    json={"name": "grp", "type": "group", "parent_id": root["id"]}).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1", "parent_id": g["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "noip", "type": "switch", "parent_id": g["id"]})
    client.post("/api/external", headers=admin_headers,
                json={"name": "ext", "domain": "example.com"})
    client.put("/api/settings/inspection-interval", headers=admin_headers,
               json={"poll_interval_minutes": 7})


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="v", password_hash=hash_password("pw123456"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "v", "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_export_default_includes_all(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers).json()
    assert data["version"] == 1
    names = [d["name"] for d in data["devices"]]
    assert names[0] == "root"
    assert names[1] == "grp"
    assert set(names) == {"root", "grp", "sw1", "noip"}
    assert data["external"][0]["name"] == "ext"
    assert data["settings"] == [{"key": "poll_interval_minutes", "value": "7"}]


def test_export_subset(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers,
                      params={"include_external": "1"}).json()
    assert "devices" not in data
    assert "settings" not in data
    assert data["external"][0]["name"] == "ext"


def test_backup_export_admin_only(client):
    vh = _mk_viewer(client)
    assert client.get("/api/backup/export", headers=vh).status_code == 403
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py`
Expected: FAIL — 404（路由未注册）。

- [ ] **Step 3: 实现**

创建 `backend/app/services/backup_service.py`：

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device, ExternalTarget, Setting, utcnow

BACKUP_VERSION = 1


def export_backup(
    db: Session,
    include_devices: bool = True,
    include_external: bool = True,
    include_settings: bool = True,
) -> dict:
    data = {"version": BACKUP_VERSION, "exported_at": utcnow().isoformat()}
    if include_devices:
        devices = list(db.scalars(select(Device).order_by(Device.order_index, Device.id)))
        data["devices"] = _flatten_devices(devices)
    if include_external:
        targets = db.scalars(select(ExternalTarget).order_by(ExternalTarget.id)).all()
        data["external"] = [
            {"name": t.name, "ip_address": t.ip_address, "domain": t.domain, "port": t.port}
            for t in targets
        ]
    if include_settings:
        rows = db.scalars(select(Setting).order_by(Setting.key)).all()
        data["settings"] = [{"key": r.key, "value": r.value} for r in rows]
    return data


def _flatten_devices(devices: list[Device]) -> list[dict]:
    by_parent: dict[int | None, list[Device]] = {}
    node_ids = {d.id for d in devices}
    for d in devices:
        by_parent.setdefault(d.parent_id, []).append(d)
    out: list[dict] = []

    def walk(d: Device) -> None:
        out.append(
            {
                "id": d.id,
                "name": d.name,
                "type": d.type,
                "ip_address": d.ip_address,
                "port": d.port,
                "order_index": d.order_index,
                "parent_id": d.parent_id,
            }
        )
        for child in sorted(by_parent.get(d.id, []), key=lambda x: (x.order_index, x.id)):
            walk(child)

    for d in sorted(devices, key=lambda x: (x.order_index, x.id)):
        if d.parent_id is None or d.parent_id not in node_ids:
            walk(d)
    return out
```

创建 `backend/app/routers/backup.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.services.backup_service import export_backup

router = APIRouter()


@router.get("/export")
def export_backup_endpoint(
    include_devices: bool | None = None,
    include_external: bool | None = None,
    include_settings: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if include_devices is None and include_external is None and include_settings is None:
        include_devices = include_external = include_settings = True
    else:
        include_devices = bool(include_devices)
        include_external = bool(include_external)
        include_settings = bool(include_settings)
    return export_backup(db, include_devices, include_external, include_settings)
```

`backend/app/main.py` 第 7 行改为：

```python
from app.routers import auth, backup, devices, external, users
```

第 29 行后追加：

```python
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py -v`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/backup_service.py backend/app/routers/backup.py backend/app/main.py backend/tests/test_backup_api.py
git commit -m "feat: add backup export API"
```

---

### Task 2: 后端备份导入（replace/merge）

**Files:**
- Modify: `backend/app/services/backup_service.py`（追加导入函数）
- Modify: `backend/app/routers/backup.py`（追加 POST /import）
- Modify: `backend/tests/test_backup_api.py`（追加导入用例）

**Interfaces:**
- Consumes: `export_backup`（Task 1）、`app.models`、`get_poll_interval`。
- Produces: `import_backup(db, data: dict, mode: str) -> None`（非法 version/缺 name/缺 ip 与 domain → `ValueError`；replace 清空重建，merge 同名跳过）。Task 3 的 reset 复用。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_backup_api.py` 末尾追加：

```python
def test_import_replace_roundtrip(client, admin_headers):
    _tree(client, admin_headers)
    data = client.get("/api/backup/export", headers=admin_headers).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "extra", "type": "switch", "ip_address": "10.0.0.99"})

    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=data)
    assert r.status_code == 200

    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"root", "grp", "sw1", "noip"}
    tree = client.get("/api/devices/tree", headers=admin_headers).json()
    assert tree[0]["name"] == "root"
    assert tree[0]["children"][0]["name"] == "grp"
    assert tree[0]["children"][0]["children"][0]["name"] == "sw1"
    assert client.get("/api/external", headers=admin_headers).json()[0]["name"] == "ext"


def test_import_merge_skips_existing_and_adds_new(client, admin_headers):
    _tree(client, admin_headers)
    backup = {
        "version": 1,
        "devices": [
            {"id": 1, "name": "root", "type": "group", "ip_address": None, "port": None,
             "order_index": 0, "parent_id": None},
            {"id": 2, "name": "grp", "type": "group", "ip_address": None, "port": None,
             "order_index": 0, "parent_id": 1},
            {"id": 3, "name": "swNEW", "type": "switch", "ip_address": "10.0.0.50",
             "port": None, "order_index": 0, "parent_id": 2},
        ],
        "external": [{"name": "ext", "ip_address": None, "domain": "example.com", "port": None}],
        "settings": [{"key": "poll_interval_minutes", "value": "3"}],
    }
    r = client.post("/api/backup/import?mode=merge", headers=admin_headers, json=backup)
    assert r.status_code == 200

    names = {d["name"] for d in client.get("/api/devices", headers=admin_headers).json()}
    assert names == {"root", "grp", "sw1", "noip", "swNEW"}
    assert len(client.get("/api/external", headers=admin_headers).json()) == 1
    got = client.get("/api/settings/inspection-interval", headers=admin_headers).json()
    assert got["poll_interval_minutes"] == 3
    grp_children = [c["name"] for c in
                    client.get("/api/devices/tree", headers=admin_headers).json()[0]["children"][0]["children"]]
    assert "swNEW" in grp_children


def test_import_invalid_version(client, admin_headers):
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json={"version": 2})
    assert r.status_code == 422


def test_import_missing_device_name(client, admin_headers):
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers,
                    json={"version": 1, "devices": [{"id": 1, "type": "group"}]})
    assert r.status_code == 422


def test_import_reschedules_interval(client, admin_headers, monkeypatch):
    from app.routers import backup as backup_router

    called = []
    monkeypatch.setattr(backup_router, "reschedule_interval", lambda m: called.append(m))
    data = {"version": 1, "settings": [{"key": "poll_interval_minutes", "value": "9"}]}
    r = client.post("/api/backup/import?mode=replace", headers=admin_headers, json=data)
    assert r.status_code == 200
    assert called and called[-1] == 9
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py`
Expected: FAIL — 新增 5 个用例：`/api/backup/import` 404 或 `import_backup` 未定义。

- [ ] **Step 3: 实现**

在 `backend/app/services/backup_service.py` 末尾追加：

```python
def import_backup(db: Session, data, mode: str) -> None:
    if not isinstance(data, dict) or data.get("version") != BACKUP_VERSION:
        raise ValueError("unsupported backup version")
    if mode == "replace":
        _import_replace(db, data)
    else:
        _import_merge(db, data)
    db.commit()


def _import_replace(db: Session, data) -> None:
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    _import_devices(db, data.get("devices", []), merge=False)
    _import_external(db, data.get("external", []), merge=False)
    _import_settings(db, data.get("settings", []))


def _import_merge(db: Session, data) -> None:
    _import_devices(db, data.get("devices", []), merge=True)
    _import_external(db, data.get("external", []), merge=True)
    _import_settings(db, data.get("settings", []))


_VALID_TYPES = {"group", "server", "switch", "terminal"}


def _import_devices(db: Session, items, merge: bool) -> None:
    id_map: dict[int, int] = {}
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("device name is required")
        dev_type = item.get("type") or "group"
        if dev_type not in _VALID_TYPES:
            raise ValueError(f"invalid device type: {dev_type}")
        parent_id = id_map.get(item.get("parent_id"))
        if merge:
            existing = db.scalars(
                select(Device).where(Device.parent_id == parent_id, Device.name == name)
            ).first()
            if existing is not None:
                id_map[item["id"]] = existing.id
                continue
        device = Device(
            name=name,
            type=dev_type,
            ip_address=item.get("ip_address"),
            port=item.get("port"),
            order_index=item.get("order_index") or 0,
            parent_id=parent_id,
        )
        db.add(device)
        db.flush()
        id_map[item["id"]] = device.id


def _import_external(db: Session, items, merge: bool) -> None:
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("external target name is required")
        if not item.get("ip_address") and not item.get("domain"):
            raise ValueError("ip_address or domain is required")
        if merge:
            existing = db.scalars(
                select(ExternalTarget).where(ExternalTarget.name == name)
            ).first()
            if existing is not None:
                continue
        db.add(
            ExternalTarget(
                name=name,
                ip_address=item.get("ip_address"),
                domain=item.get("domain"),
                port=item.get("port"),
            )
        )


def _import_settings(db: Session, items) -> None:
    for item in items:
        key = (item.get("key") or "").strip()
        if not key:
            raise ValueError("setting key is required")
        value = item.get("value") or ""
        existing = db.get(Setting, key)
        if existing is None:
            db.add(Setting(key=key, value=value))
        else:
            existing.value = value
```

`backend/app/routers/backup.py` 的 import 改为：

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.backup_service import export_backup, import_backup
from app.services.setting_service import get_poll_interval
```

并在 `export_backup_endpoint` 之后追加：

```python
@router.post("/import")
async def import_backup_endpoint(
    request: Request,
    mode: str = Query("replace", pattern="^(replace|merge)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="invalid JSON body")
    try:
        import_backup(db, data, mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    reschedule_interval(get_poll_interval(db))
    return {"ok": True, "mode": mode}
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py -v`
Expected: 8 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/backup_service.py backend/app/routers/backup.py backend/tests/test_backup_api.py
git commit -m "feat: add backup import API with replace and merge modes"
```

---

### Task 3: 清除所有数据（reset）

**Files:**
- Modify: `backend/app/services/backup_service.py`（追加 `reset_all`）
- Modify: `backend/app/routers/backup.py`（追加 POST /reset）
- Modify: `backend/tests/test_backup_api.py`（追加 reset 用例）

**Interfaces:**
- Consumes: `export_backup/import_backup`（Task 1/2）、`app.database.seed_default_admin`。
- Produces: `reset_all(db) -> None`（清空 Device/ExternalTarget/Setting/User 并重建默认 admin）。Task 7 前端「清除所有数据」调用对应 API。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_backup_api.py` 末尾追加：

```python
def test_reset_clears_and_reseeds_admin(client, admin_headers):
    _tree(client, admin_headers)
    client.post("/api/users", headers=admin_headers,
                json={"username": "u1", "password": "pw123456", "role": "viewer"})

    r = client.post("/api/backup/reset", headers=admin_headers)
    assert r.status_code == 200

    assert client.get("/api/devices", headers=admin_headers).json() == []
    assert client.get("/api/external", headers=admin_headers).json() == []
    got = client.get("/api/settings/inspection-interval", headers=admin_headers).json()
    assert got["poll_interval_minutes"] == 5
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert me["username"] == "admin"
    assert client.post("/api/auth/login",
                       json={"username": "u1", "password": "pw123456"}).status_code == 401


def test_reset_reschedules_interval(client, admin_headers, monkeypatch):
    from app.config import settings as app_settings
    from app.routers import backup as backup_router

    called = []
    monkeypatch.setattr(backup_router, "reschedule_interval", lambda m: called.append(m))
    client.post("/api/backup/reset", headers=admin_headers)
    assert called and called[-1] == app_settings.poll_interval_minutes


def test_backup_import_and_reset_admin_only(client):
    vh = _mk_viewer(client)
    assert client.post("/api/backup/import?mode=replace", headers=vh,
                       json={"version": 1}).status_code == 403
    assert client.post("/api/backup/reset", headers=vh).status_code == 403
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py`
Expected: FAIL — `/api/backup/reset` 404。

- [ ] **Step 3: 实现**

`backend/app/services/backup_service.py` 顶部 import 追加 `seed_default_admin`：

```python
from app.database import seed_default_admin
from app.models import Device, ExternalTarget, Setting, User, utcnow
```

末尾追加：

```python
def reset_all(db: Session) -> None:
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    db.query(User).delete()
    db.commit()
    seed_default_admin()
```

`backend/app/routers/backup.py` 的 import 改为：

```python
from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.backup_service import export_backup, import_backup, reset_all
from app.services.setting_service import get_poll_interval
```

并在 `import_backup_endpoint` 之后追加：

```python
@router.post("/reset")
def reset_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    reset_all(db)
    reschedule_interval(settings.poll_interval_minutes)
    return {"ok": True}
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_backup_api.py -v`
Expected: 11 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/backup_service.py backend/app/routers/backup.py backend/tests/test_backup_api.py
git commit -m "feat: add clear-all reset endpoint"
```

---

### Task 4: 前端 users API + store

**Files:**
- Create: `frontend/src/api/users.js`
- Create: `frontend/src/stores/users.js`
- Create: `frontend/src/stores/__tests__/users.spec.js`

**Interfaces:**
- Consumes: `frontend/src/api/client`。
- Produces: `fetchUsers()`、`createUser(payload)`、`updateUser(id, payload)`、`deleteUser(id)`；`useUsersStore()`（state `users/loading`，actions `load()/create()/update()/remove()`）。Task 5 复用全部。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/stores/__tests__/users.spec.js`：

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { fetchMock, createMock, updateMock, removeMock, loadMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/users', () => ({
  fetchUsers: fetchMock,
  createUser: createMock,
  updateUser: updateMock,
  deleteUser: removeMock,
}))

import { useUsersStore } from '../users'

describe('users store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('load fetches users', async () => {
    fetchMock.mockResolvedValue({ data: [{ id: 1, username: 'admin' }] })
    const store = useUsersStore()
    await store.load()
    expect(store.users).toHaveLength(1)
  })

  it('create then reload', async () => {
    createMock.mockResolvedValue({ data: {} })
    const store = useUsersStore()
    store.load = loadMock
    await store.create({ username: 'x', password: 'pw123456', role: 'viewer' })
    expect(createMock).toHaveBeenCalledWith({ username: 'x', password: 'pw123456', role: 'viewer' })
    expect(loadMock).toHaveBeenCalledTimes(1)
  })

  it('remove then reload', async () => {
    removeMock.mockResolvedValue({})
    const store = useUsersStore()
    store.load = loadMock
    await store.remove(2)
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/users.spec.js`
Expected: FAIL — `Cannot find module '../../api/users'`。

- [ ] **Step 3: 实现**

创建 `frontend/src/api/users.js`：

```js
import client from './client'

export function fetchUsers() {
  return client.get('/users')
}

export function createUser(payload) {
  return client.post('/users', payload)
}

export function updateUser(id, payload) {
  return client.put(`/users/${id}`, payload)
}

export function deleteUser(id) {
  return client.delete(`/users/${id}`)
}
```

创建 `frontend/src/stores/users.js`：

```js
import { defineStore } from 'pinia'
import { createUser, deleteUser, fetchUsers, updateUser } from '../api/users'

export const useUsersStore = defineStore('users', {
  state: () => ({
    users: [],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.users = (await fetchUsers()).data
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createUser(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateUser(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteUser(id)
      await this.load()
    },
  },
})
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/users.spec.js`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/users.js frontend/src/stores/users.js frontend/src/stores/__tests__/users.spec.js
git commit -m "feat: add users api and store on frontend"
```

---

### Task 5: UsersPanel 用户管理组件

**Files:**
- Create: `frontend/src/components/UsersPanel.vue`
- Create: `frontend/src/components/__tests__/UsersPanel.spec.js`

**Interfaces:**
- Consumes: `useUsersStore()`（Task 4）。
- Produces: `<UsersPanel />` 组件（列表 + 新增/编辑/删除；编辑只改角色+可选密码）。Task 7 放入 MainView。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/components/__tests__/UsersPanel.spec.js`：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { loadMock, createMock, updateMock, removeMock, successMock, errorMock, confirmMock } = vi.hoisted(() => ({
  loadMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  confirmMock: vi.fn(),
}))

const users = vi.hoisted(() => [
  { id: 1, username: 'admin', role: 'admin', created_at: '2026-01-01T00:00:00' },
  { id: 2, username: 'u1', role: 'viewer', created_at: '2026-01-02T00:00:00' },
])

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('../../stores/users', () => ({
  useUsersStore: () => ({
    users,
    load: loadMock,
    create: createMock,
    update: updateMock,
    remove: removeMock,
  }),
}))

import UsersPanel from '../UsersPanel.vue'

function mountPanel() {
  return mount(UsersPanel, {
    global: {
      stubs: {
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input class="t-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select class="role-select" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': {
          props: ['value'],
          template: '<option :value="value"><slot /></option>',
        },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

describe('UsersPanel 用户管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载后加载用户列表并渲染', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('u1')
  })

  it('新增用户提交用户名/密码/角色', async () => {
    createMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '新增用户').trigger('click')
    await wrapper.findAll('.dlg input.t-input').at(0).setValue('u2')
    await wrapper.findAll('.dlg input.t-input').at(1).setValue('pw123456')
    await wrapper.find('.dlg select.role-select').setValue('admin')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ username: 'u2', password: 'pw123456', role: 'admin' })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('编辑用户改角色且可选重置密码', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '编辑').trigger('click')
    await wrapper.find('.dlg select.role-select').setValue('admin')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(2, { role: 'admin' })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('删除用户需确认并调用 remove', async () => {
    confirmMock.mockResolvedValue()
    removeMock.mockResolvedValue()
    const wrapper = mountPanel()
    await flushPromises()
    const deleteButtons = wrapper.findAll('button').filter((b) => b.text() === '删除')
    await deleteButtons[1].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(successMock).toHaveBeenCalledWith('已删除')
  })

  it('删除自己被拒时提示后端错误', async () => {
    confirmMock.mockResolvedValue()
    removeMock.mockRejectedValue({ response: { data: { detail: 'cannot delete yourself' } } })
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('cannot delete yourself')
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/UsersPanel.spec.js`
Expected: FAIL — `Cannot find module '../UsersPanel.vue'`。

- [ ] **Step 3: 实现**

创建 `frontend/src/components/UsersPanel.vue`：

```vue
<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUsersStore } from '../stores/users'

const store = useUsersStore()
const dialogVisible = ref(false)
const editing = ref(null)
const form = ref({ username: '', password: '', role: 'viewer' })

onMounted(() => store.load())

function openCreate() {
  editing.value = null
  form.value = { username: '', password: '', role: 'viewer' }
  dialogVisible.value = true
}

function openEdit(user) {
  editing.value = user
  form.value = { username: user.username, password: '', role: user.role }
  dialogVisible.value = true
}

async function onSave() {
  try {
    if (editing.value) {
      const payload = { role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await store.update(editing.value.id, payload)
    } else {
      await store.create({
        username: form.value.username,
        password: form.value.password,
        role: form.value.role,
      })
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function onDelete(user) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${user.username}」？`, '删除确认')
  } catch (error) {
    return
  }
  try {
    await store.remove(user.id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增用户</el-button>
        <el-button @click="store.load()">刷新</el-button>
      </div>
    </template>
    <table class="users-table">
      <thead>
        <tr>
          <th>用户名</th>
          <th>角色</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in store.users" :key="u.id">
          <td>{{ u.username }}</td>
          <td>
            <el-tag :type="u.role === 'admin' ? 'danger' : 'info'">{{ u.role }}</el-tag>
          </td>
          <td>{{ u.created_at }}</td>
          <td>
            <el-button size="small" @click="openEdit(u)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDelete(u)">删除</el-button>
          </td>
        </tr>
      </tbody>
    </table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password"
                    :placeholder="editing ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="管理员" value="admin" />
            <el-option label="只读用户" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/UsersPanel.spec.js`
Expected: 5 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/UsersPanel.vue frontend/src/components/__tests__/UsersPanel.spec.js
git commit -m "feat: add user management panel"
```

---

### Task 6: 前端 backup API + BackupPanel 组件

**Files:**
- Create: `frontend/src/api/backup.js`
- Create: `frontend/src/components/BackupPanel.vue`
- Create: `frontend/src/components/__tests__/BackupPanel.spec.js`

**Interfaces:**
- Consumes: `exportBackup/importBackup/resetData`（本任务）、`useDevicesStore().load()`、`useExternalStore().load()`、`useSettingsStore().loadInterval()`、`useAuthStore().logout()`、`useRouter().push()`。
- Produces: `<BackupPanel />` 组件（导出勾选+下载、导入文件+模式、清除需确认）。Task 7 放入 MainView。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/components/__tests__/BackupPanel.spec.js`：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  exportMock,
  importMock,
  resetMock,
  successMock,
  errorMock,
  promptMock,
  loadMock,
  extLoadMock,
  loadIntervalMock,
  logoutMock,
  pushMock,
} = vi.hoisted(() => ({
  exportMock: vi.fn(),
  importMock: vi.fn(),
  resetMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  promptMock: vi.fn(),
  loadMock: vi.fn(),
  extLoadMock: vi.fn(),
  loadIntervalMock: vi.fn(),
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock },
}))

vi.mock('../../api/backup', () => ({
  exportBackup: exportMock,
  importBackup: importMock,
  resetData: resetMock,
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({ load: loadMock }),
}))

vi.mock('../../stores/external', () => ({
  useExternalStore: () => ({ load: extLoadMock }),
}))

vi.mock('../../stores/settings', () => ({
  useSettingsStore: () => ({ loadInterval: loadIntervalMock }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' }, logout: logoutMock }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

import BackupPanel from '../BackupPanel.vue'

function mountPanel() {
  return mount(BackupPanel, {
    global: {
      stubs: {
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

describe('BackupPanel 备份与恢复', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('导出默认勾选全部三类', async () => {
    exportMock.mockResolvedValue({ data: { version: 1 } })
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '导出备份').trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledWith({
      include_devices: true,
      include_external: true,
      include_settings: true,
    })
  })

  it('取消勾选外网后导出参数排除外网', async () => {
    exportMock.mockResolvedValue({ data: { version: 1 } })
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)
    await buttonByText(wrapper, '导出备份').trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledWith({
      include_devices: true,
      include_external: false,
      include_settings: true,
    })
  })

  it('导入上传文件后调用 import 并刷新数据', async () => {
    importMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    const file = new File([JSON.stringify({ version: 1 })], 'backup.json',
                          { type: 'application/json' })
    const input = wrapper.find('input.file-input')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(importMock).toHaveBeenCalledWith({ version: 1 }, 'replace')
    expect(loadMock).toHaveBeenCalled()
    expect(extLoadMock).toHaveBeenCalled()
    expect(successMock).toHaveBeenCalledWith('导入成功')
  })

  it('清除所有数据需输入 clear 确认后登出跳转', async () => {
    promptMock.mockResolvedValue({ value: 'clear' })
    resetMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '清除所有数据（初始化）').trigger('click')
    await flushPromises()
    expect(resetMock).toHaveBeenCalled()
    expect(logoutMock).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('清除取消时不做任何事', async () => {
    promptMock.mockRejectedValue('cancel')
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '清除所有数据（初始化）').trigger('click')
    await flushPromises()
    expect(resetMock).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/BackupPanel.spec.js`
Expected: FAIL — `Cannot find module '../BackupPanel.vue'`。

- [ ] **Step 3: 实现**

创建 `frontend/src/api/backup.js`：

```js
import client from './client'

export function exportBackup(params) {
  return client.get('/backup/export', { params })
}

export function importBackup(data, mode) {
  return client.post('/backup/import', data, { params: { mode } })
}

export function resetData() {
  return client.post('/backup/reset')
}
```

创建 `frontend/src/components/BackupPanel.vue`：

```vue
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { exportBackup, importBackup, resetData } from '../api/backup'
import { useAuthStore } from '../stores/auth'
import { useDevicesStore } from '../stores/devices'
import { useExternalStore } from '../stores/external'
import { useSettingsStore } from '../stores/settings'

const router = useRouter()
const auth = useAuthStore()
const devices = useDevicesStore()
const external = useExternalStore()
const settings = useSettingsStore()

const includeDevices = ref(true)
const includeExternal = ref(true)
const includeSettings = ref(true)
const importMode = ref('replace')

async function onExport() {
  try {
    const { data } = await exportBackup({
      include_devices: includeDevices.value,
      include_external: includeExternal.value,
      include_settings: includeSettings.value,
    })
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    a.href = url
    a.download = `weaver-backup-${stamp}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导出失败')
  }
}

async function onImport(file) {
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    await importBackup(data, importMode.value)
    await Promise.all([devices.load(), external.load()])
    if (auth.user?.role === 'admin') await settings.loadInterval()
    ElMessage.success('导入成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

function onFileChange(event) {
  const file = event.target.files[0]
  if (file) onImport(file)
}

async function onReset() {
  let value
  try {
    const result = await ElMessageBox.prompt(
      '输入 "clear" 确认清除所有数据',
      '危险操作',
      { inputPattern: /^clear$/, inputErrorMessage: '请输入 clear' }
    )
    value = result.value
  } catch (error) {
    return
  }
  if (value !== 'clear') return
  try {
    await resetData()
    auth.logout()
    router.push('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '清除失败')
  }
}
</script>

<template>
  <div class="backup-panel">
    <el-card class="section">
      <template #header>导出备份</template>
      <div class="checks">
        <label><input type="checkbox" v-model="includeDevices" /> 设备</label>
        <label><input type="checkbox" v-model="includeExternal" /> 外网目标</label>
        <label><input type="checkbox" v-model="includeSettings" /> 巡检间隔</label>
      </div>
      <el-button type="primary" @click="onExport">导出备份</el-button>
    </el-card>

    <el-card class="section">
      <template #header>导入备份</template>
      <div class="mode">
        <label><input type="radio" value="replace" v-model="importMode" /> 替换</label>
        <label><input type="radio" value="merge" v-model="importMode" /> 合并</label>
      </div>
      <input class="file-input" type="file" accept="application/json,.json" @change="onFileChange" />
    </el-card>

    <el-card class="section danger">
      <template #header>危险操作</template>
      <p>清除所有数据将清空设备、外网目标、设置与所有用户，仅保留默认 admin。</p>
      <el-button type="danger" @click="onReset">清除所有数据（初始化）</el-button>
    </el-card>
  </div>
</template>
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/BackupPanel.spec.js`
Expected: 5 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/backup.js frontend/src/components/BackupPanel.vue frontend/src/components/__tests__/BackupPanel.spec.js
git commit -m "feat: add backup and restore panel"
```

---

### Task 7: MainView 集成（页签）+ 全量回归 + 构建

**Files:**
- Modify: `frontend/src/views/MainView.vue`（追加两个 admin-only 页签）
- Modify: `frontend/src/views/__tests__/MainView.spec.js`（追加页签可见性用例）

**Interfaces:**
- Consumes: `UsersPanel.vue`（Task 5）、`BackupPanel.vue`（Task 6）、现有 `isAdmin` computed。
- Produces: MainView 含「用户管理」「备份与恢复」两个 `el-tab-pane`（`v-if="isAdmin"`）。

- [ ] **Step 1: 写失败测试**

修改 `frontend/src/views/__tests__/MainView.spec.js`：
- 在 stubs 里新增两个组件 stub：

```js
        UsersPanel: { template: '<div class="users-panel-stub" />' },
        BackupPanel: { template: '<div class="backup-panel-stub" />' },
```

- 将 `el-tab-pane` stub 改为带 label：

```js
        'el-tab-pane': { template: '<div :data-label="$attrs.label"><slot /></div>' },
```

- 末尾追加：

```js
describe('MainView 管理页签', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示用户管理与备份与恢复页签', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-label="用户管理"]').exists()).toBe(true)
    expect(wrapper.find('[data-label="备份与恢复"]').exists()).toBe(true)
  })

  it('viewer 不显示管理页签', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-label="用户管理"]').exists()).toBe(false)
    expect(wrapper.find('[data-label="备份与恢复"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: FAIL — 新增 2 个用例失败（页签不存在）。

- [ ] **Step 3: 实现**

`frontend/src/views/MainView.vue` 的 `<script setup>` 追加 import：

```js
import UsersPanel from '../components/UsersPanel.vue'
import BackupPanel from '../components/BackupPanel.vue'
```

在 `el-tabs` 内、外网页签之后追加两个页签：

```html
        <el-tab-pane v-if="isAdmin" label="用户管理" name="users">
          <UsersPanel />
        </el-tab-pane>
        <el-tab-pane v-if="isAdmin" label="备份与恢复" name="backup">
          <BackupPanel />
        </el-tab-pane>
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: 13 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: add user and backup tabs to MainView"
```

---

### Task 8: 全量回归 + 构建

- [ ] **Step 1: 后端回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 passed（67 原有 + backup 11 ≈ 78；以实际输出为准）。

- [ ] **Step 2: 前端回归 + 构建**

Run（workdir=`frontend`）: `npm run test`
Expected: 全部 passed（23 原有 + users 3 + UsersPanel 5 + BackupPanel 5 + MainView 2 ≈ 38；以实际输出为准）。

Run（workdir=`frontend`）: `npm run build`
Expected: `✓ built in ...`，仅有既存 chunk 大小警告。

- [ ] **Step 3: 提交任何遗漏**

`git status --short` 确认无未提交改动。`git log --oneline -10` 确认本计划 7 个提交（feat ×7）就位。

---

## Self-Review 备注

- **spec 覆盖**：导出默认全类别+可勾选子集 ✓（Task 1）；导入 replace/merge 可选 ✓（Task 2）；清除所有数据并重建 admin ✓（Task 3）；用户管理前端 ✓（Task 4/5）；备份面板 ✓（Task 6）；MainView 页签 admin-only ✓（Task 7）。
- **类型一致**：`export_backup/import_backup/reset_all` 均在 backup_service 定义并跨 Task 1-3 复用；`useUsersStore` 的 load/create/update/remove 在 Task 4 定义、Task 5 消费；`exportBackup/importBackup/resetData` 在 Task 6 定义并被 BackupPanel 使用。
- **注意**：导入用 `request.json()` 而非 UploadFile（未装 python-multipart）；`reset_all` 通过 `seed_default_admin()` 重建 admin，测试中 admin token（sub=1）在清空后仍有效（SQLite rowid 复用）。
