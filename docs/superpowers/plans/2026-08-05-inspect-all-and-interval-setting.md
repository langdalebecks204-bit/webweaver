# 立即巡检全部 + 巡检间隔自定义 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「立即巡检全部」按钮（admin+viewer 可用，触发后端全量巡检并自动刷新树），并把自动巡检间隔做成界面可设置（仅 admin，运行时生效 + 存库持久化，单位分钟，范围 1~1440）。

**Architecture:** 后端新增 `Setting` 键值表存 `poll_interval_minutes`，新增 `GET/PUT /api/settings/inspection-interval`（PUT 写库 + 通过 scheduler 模块级 `_scheduler` 引用调用 `reschedule_job` 重排作业）；`POST /api/devices/recheck-all` 复用从调度器抽取的 `collect_all_targets()` 查询 + 现有 `run_inspection()`。前端新增 `api/settings.js`、`stores/settings.js`，`MainView.vue` 工具栏加「立即巡检全部」按钮（所有人）与间隔设置控件（仅 admin）；devices store 加 `recheckAll()` action。

**Tech Stack:** FastAPI + SQLAlchemy + APScheduler + Pydantic（后端）；Vue 3 + Pinia + Element Plus + Vitest（前端）。

## Global Constraints

- 后端测试（workdir=backend）：`.venv\Scripts\python.exe -m pytest tests`，当前 38 passed。前端（workdir=frontend）：`npm run test`，当前 9 passed；构建 `npm run build`。
- 后端测试 fixture：`conftest.py` 的 `clean_db`（autouse）会清空 `Device`、`User` 表（临时库 `weaver_test_<pid>.db`）。`WEAVER_ENABLE_SCHEDULER=0`。
- `recheck-all` 权限：`get_current_user`（admin + viewer）。`inspection-interval` GET/PUT 权限：`require_admin`。
- 间隔校验：pydantic `Field(ge=1, le=1440)`（超范围 422）。默认值回退 env `settings.poll_interval_minutes`（=5）。
- 巡检全部：查询 `Device.ip_address.is_not(None) and Device.type != "group"`，复用 `run_inspection`（已带并发信号量与 commit）。
- 无代码注释（除非必需）。提交信息以 `feat:`/`test:`/`docs:` 前缀开头。
- 分支 `feature/phase1-minimal-loop`，worktree `D:\code\WebWeaver\.worktrees\phase1-minimal-loop`。
- 前端测试用 Vitest + `@vue/test-utils` + `happy-dom`。组件测试文件首行 `// @vitest-environment happy-dom`；store 纯逻辑测试用 `node` 环境（不写该注释行）。

---

### Task 1: 后端 Setting 表 + settings 路由（GET/PUT）

**Files:**
- Modify: `backend/app/models.py:33-41`（追加 Setting 类）
- Create: `backend/app/services/setting_service.py`
- Create: `backend/app/routers/settings.py`
- Modify: `backend/app/main.py:7,26-27`（注册路由）
- Modify: `backend/app/database.py:35`（init_db import Setting）
- Create: `backend/tests/test_settings_api.py`
- Modify: `backend/app/inspector/scheduler.py`（最小 `_scheduler` + `reschedule_interval`，Task 2 再补 DB 驱动）

**Interfaces:**
- Consumes: `app.database.SessionLocal/get_db`、`app.deps.require_admin`、`app.config.settings`（默认间隔）。
- Produces: `app.services.setting_service.get_poll_interval(db) -> int`、`set_poll_interval(db, minutes) -> int`；`app.inspector.scheduler.reschedule_interval(minutes) -> None`（Task 2 复用）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_settings_api.py`：

```python
from app.database import SessionLocal
from app.models import Setting, User
from app.security import hash_password


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="viewer1", password_hash=hash_password("viewpass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewpass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_interval_returns_default(client, admin_headers):
    r = client.get("/api/settings/inspection-interval", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"poll_interval_minutes": 5}


def test_put_interval_persists_and_returns(client, admin_headers):
    r = client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 30},
    )
    assert r.status_code == 200
    assert r.json() == {"poll_interval_minutes": 30}

    got = client.get("/api/settings/inspection-interval", headers=admin_headers)
    assert got.json() == {"poll_interval_minutes": 30}

    with SessionLocal() as db:
        row = db.get(Setting, "poll_interval_minutes")
        assert row is not None
        assert row.value == "30"


def test_put_interval_reschedules(client, admin_headers, monkeypatch):
    calls = []

    def fake_reschedule(minutes):
        calls.append(minutes)

    monkeypatch.setattr("app.routers.settings.reschedule_interval", fake_reschedule)
    r = client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 10},
    )
    assert r.status_code == 200
    assert calls == [10]


def test_interval_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/settings/inspection-interval", headers=vh).status_code == 403
    assert client.put(
        "/api/settings/inspection-interval",
        headers=vh,
        json={"poll_interval_minutes": 10},
    ).status_code == 403


def test_interval_out_of_range(client, admin_headers):
    assert client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 0},
    ).status_code == 422
    assert client.put(
        "/api/settings/inspection-interval",
        headers=admin_headers,
        json={"poll_interval_minutes": 1441},
    ).status_code == 422
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_settings_api.py`
Expected: FAIL — `ImportError: cannot import name 'Setting'`（模型不存在）。

- [ ] **Step 3: 实现**

在 `backend/app/models.py` 的 `User` 类后追加：

```python
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
```

创建 `backend/app/services/setting_service.py`：

```python
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

POLL_INTERVAL_KEY = "poll_interval_minutes"


def get_poll_interval(db: Session) -> int:
    row = db.get(Setting, POLL_INTERVAL_KEY)
    if row is None:
        return settings.poll_interval_minutes
    return int(row.value)


def set_poll_interval(db: Session, minutes: int) -> int:
    row = db.get(Setting, POLL_INTERVAL_KEY)
    if row is None:
        db.add(Setting(key=POLL_INTERVAL_KEY, value=str(minutes)))
    else:
        row.value = str(minutes)
    db.commit()
    return minutes
```

修改 `backend/app/inspector/scheduler.py`（当前第 24 行 `def create_scheduler` 之前）追加模块级变量与函数：

```python
_scheduler: AsyncIOScheduler | None = None


def reschedule_interval(minutes: int) -> None:
    if _scheduler is not None:
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler.reschedule_job("inspection", trigger=IntervalTrigger(minutes=minutes))
```

创建 `backend/app/routers/settings.py`：

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.setting_service import get_poll_interval, set_poll_interval

router = APIRouter()


class InspectionIntervalUpdate(BaseModel):
    poll_interval_minutes: int = Field(ge=1, le=1440)


@router.get("/inspection-interval")
def get_inspection_interval(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"poll_interval_minutes": get_poll_interval(db)}


@router.put("/inspection-interval")
def update_inspection_interval(
    payload: InspectionIntervalUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    minutes = set_poll_interval(db, payload.poll_interval_minutes)
    reschedule_interval(minutes)
    return {"poll_interval_minutes": minutes}
```

修改 `backend/app/main.py`：第 7 行 `from app.routers import auth, devices, settings, users`；在第 27 行后追加：

```python
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
```

修改 `backend/app/database.py` 第 35 行：

```python
    from app.models import Device, Setting, User  # noqa: F401
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_settings_api.py -v`
Expected: 5 passed。注意：`test_put_interval_persists_and_returns` 会写库，`clean_db` fixture 目前只清 Device/User 不清 Setting —— 测试顺序内 `test_get_interval_returns_default` 先跑（在文件内靠前），且 `test_put...` 在它之后，顺序执行时默认值断言不受影响。若需绝对隔离，可后续 Task 把 `Setting` 加入 clean_db（见 Task 3 备注）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/app/services/setting_service.py backend/app/routers/settings.py backend/app/inspector/scheduler.py backend/app/main.py backend/app/database.py backend/tests/test_settings_api.py
git commit -m "feat: add inspection interval setting API persisted in DB"
```

---

### Task 2: 调度器 DB 驱动间隔 + collect_all_targets 抽取

**Files:**
- Modify: `backend/app/inspector/scheduler.py`
- Modify: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `app.services.setting_service.get_poll_interval(db)`、`SessionLocal`。
- Produces: `collect_all_targets(db) -> list[Device]`（Task 3 复用）；`create_scheduler()` 启动间隔取 DB 值；`_scheduler` 全局在 `create_scheduler` 内赋值。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_scheduler.py` 末尾追加：

```python
def test_create_scheduler_reads_interval_from_db():
    from app.database import SessionLocal
    from app.services.setting_service import set_poll_interval

    with SessionLocal() as db:
        set_poll_interval(db, 10)

    scheduler = create_scheduler()
    try:
        job = scheduler.get_job("inspection")
        assert job is not None
        assert job.trigger.interval.seconds == 600
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_reschedule_interval_changes_job_trigger():
    from app.inspector.scheduler import reschedule_interval

    scheduler = create_scheduler()
    try:
        reschedule_interval(3)
        job = scheduler.get_job("inspection")
        assert job.trigger.interval.seconds == 180
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        from app.inspector.scheduler import _scheduler

        globals()["_scheduler"] = None


def test_collect_all_targets_filters():
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.inspector.scheduler import collect_all_targets
    from app.models import Device

    with SessionLocal() as db:
        root = Device(name="root", type="group")
        db.add(root)
        db.commit()
        db.add_all(
            [
                Device(name="sw1", type="switch", ip_address="10.0.0.1", parent_id=root.id),
                Device(name="sw2", type="switch", ip_address="10.0.0.2", parent_id=root.id),
                Device(name="noip", type="switch", parent_id=root.id),
                Device(name="sub", type="group", ip_address="10.0.0.9", parent_id=root.id),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        names = sorted(d.name for d in collect_all_targets(db))
        assert names == ["sw1", "sw2"]
```

注意：`test_reschedule_interval_changes_job_trigger` 里 `globals()["_scheduler"] = None` 是把 pytest 模块命名空间里的名字置空，不会清掉 `scheduler` 模块的全局 `_scheduler`（它由 `create_scheduler` 重新赋值）。此清理是防泄漏（下个用例再 `create_scheduler` 会覆盖），无需纠结。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_all_targets'`；`test_create_scheduler_reads_interval_from_db` 得到 300 秒而非 600。

- [ ] **Step 3: 实现**

整体替换 `backend/app/inspector/scheduler.py` 为：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Device
from app.services.setting_service import get_poll_interval

_scheduler: AsyncIOScheduler | None = None


def collect_all_targets(db) -> list[Device]:
    return list(
        db.scalars(
            select(Device).where(Device.ip_address.is_not(None), Device.type != "group")
        )
    )


async def scheduled_inspection() -> None:
    from app.inspector.engine import run_inspection

    with SessionLocal() as db:
        devices = collect_all_targets(db)
        if devices:
            await run_inspection(db, devices)


def reschedule_interval(minutes: int) -> None:
    if _scheduler is not None:
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler.reschedule_job("inspection", trigger=IntervalTrigger(minutes=minutes))


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    with SessionLocal() as db:
        minutes = get_poll_interval(db)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_inspection,
        "interval",
        minutes=minutes,
        id="inspection",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler = scheduler
    return scheduler
```

注意：保留 `from app.config import settings` import（虽未被直接使用，但保持模块已有行为；若 lint 报未使用可删）。`collect_all_targets` 的 `db` 参数类型为 `sqlalchemy.orm.Session`，为简洁可用 `db` 直接标注（`from sqlalchemy.orm import Session` + `db: Session`）或省略——按现有 `scheduled_inspection` 风格省略即可。

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_scheduler.py tests/test_settings_api.py -v`
Expected: 全部 passed（scheduler 4 + settings 5）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/inspector/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: make scheduler interval DB-driven and extract collect_all_targets"
```

---

### Task 3: 后端 recheck-all 接口

**Files:**
- Modify: `backend/app/routers/devices.py`
- Modify: `backend/tests/test_devices_api.py`
- Modify: `backend/tests/conftest.py`（clean_db 清 Setting，防 Task1 写库污染其他测试）

**Interfaces:**
- Consumes: `app.inspector.scheduler.collect_all_targets(db)`、`app.inspector.engine.run_inspection(db, targets)`、`get_current_user`。
- Produces: `POST /api/devices/recheck-all` → `{"checked": [device_dict, ...]}`。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_devices_api.py` 末尾追加：

```python
def test_recheck_all_devices(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=5)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"}).json()
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw1", "type": "switch", "ip_address": "10.0.0.1", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "sw2", "type": "switch", "ip_address": "10.0.0.2", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "noip", "type": "switch", "parent_id": root["id"]})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "grp", "type": "group", "parent_id": root["id"]})

    r = client.post("/api/devices/recheck-all", headers=admin_headers)
    assert r.status_code == 200
    checked = r.json()["checked"]
    assert len(checked) == 2
    assert all(c["status"] == "online" for c in checked)


def test_recheck_all_viewer_allowed(client):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    r = client.post("/api/devices/recheck-all", headers=vh)
    assert r.status_code == 200
    assert r.json() == {"checked": []}


def test_recheck_all_requires_auth(client):
    assert client.post("/api/devices/recheck-all").status_code == 401
```

修改 `backend/tests/conftest.py`：第 21 行 `from app.models import Device, User` 改为：

```python
        from app.models import Device, Setting, User
```

并在两个 `db.query(...).delete()` 之间/之后补 `db.query(Setting).delete()`（共两处，teardown 也要清）：

```python
    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(Setting).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(Setting).delete()
        db.query(User).delete()
        db.commit()
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_devices_api.py -v`
Expected: FAIL — 404（`/recheck-all` 未注册，FastAPI 返回 404 Not Found）。

- [ ] **Step 3: 实现**

修改 `backend/app/routers/devices.py`：
- 第 7 行 import 处追加 `from app.inspector.scheduler import collect_all_targets`。
- 在 `get_tree`（第 47 行 return）之后、`get_device` 之前插入：

```python
@router.post("/recheck-all")
async def recheck_all_devices(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    targets = collect_all_targets(db)
    results = await run_inspection(db, targets)
    return {"checked": results}
```

注意路由顺序：`/recheck-all` 必须声明在 `/{device_id}`（GET）和 `/{device_id}/recheck`（POST）之前。放 `get_tree` 后即满足（GET `/{device_id}` 在第 49 行）。POST 方法路径 `/recheck-all` 与 `/{device_id}/recheck` 无歧义，但保持顺序清晰。

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 passed（现有 38 + settings 5 + scheduler 新增 3 + recheck 3 + conftest 改动 = 49）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/devices.py backend/tests/test_devices_api.py backend/tests/conftest.py
git commit -m "feat: add recheck-all endpoint to inspect every device"
```

---

### Task 4: 前端 recheck-all 与 settings store

**Files:**
- Modify: `frontend/src/api/devices.js`
- Modify: `frontend/src/stores/devices.js`
- Create: `frontend/src/api/settings.js`
- Create: `frontend/src/stores/settings.js`
- Create: `frontend/src/stores/__tests__/settings.spec.js`
- Create: `frontend/src/stores/__tests__/devices.spec.js`

**Interfaces:**
- Consumes: `frontend/src/api/client`（axios，baseURL `/api`，自动带 Bearer）。
- Produces: `recheckAllDevices()`（POST `/devices/recheck-all`）；`useDevicesStore().recheckAll()`；`fetchInspectionInterval()`（GET `/settings/inspection-interval`）；`updateInspectionInterval(minutes)`（PUT）；`useSettingsStore()`（state `pollIntervalMinutes`、actions `loadInterval()`/`saveInterval(minutes)`）。Task 5 复用全部。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/stores/__tests__/settings.spec.js`：

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { fetchMock, updateMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('../../api/settings', () => ({
  fetchInspectionInterval: fetchMock,
  updateInspectionInterval: updateMock,
}))

import { useSettingsStore } from '../settings'

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadInterval fetches current interval', async () => {
    fetchMock.mockResolvedValue({ data: { poll_interval_minutes: 30 } })
    const store = useSettingsStore()
    await store.loadInterval()
    expect(store.pollIntervalMinutes).toBe(30)
  })

  it('saveInterval updates api and state', async () => {
    updateMock.mockResolvedValue({ data: { poll_interval_minutes: 15 } })
    const store = useSettingsStore()
    await store.saveInterval(15)
    expect(updateMock).toHaveBeenCalledWith({ poll_interval_minutes: 15 })
    expect(store.pollIntervalMinutes).toBe(15)
  })
})
```

创建 `frontend/src/stores/__tests__/devices.spec.js`：

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { recheckAllMock, loadMock } = vi.hoisted(() => ({
  recheckAllMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/devices', () => ({
  createDevice: vi.fn(),
  deleteDevice: vi.fn(),
  fetchTree: vi.fn(),
  recheckAllDevices: recheckAllMock,
  recheckDevice: vi.fn(),
  updateDevice: vi.fn(),
}))

import { useDevicesStore } from '../devices'

describe('devices store recheckAll', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('calls recheck-all api then reloads tree', async () => {
    recheckAllMock.mockResolvedValue({})
    const store = useDevicesStore()
    store.load = loadMock
    await store.recheckAll()
    expect(recheckAllMock).toHaveBeenCalled()
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/settings.spec.js src/stores/__tests__/devices.spec.js`
Expected: FAIL — 模块不存在（`Cannot find module '../../api/settings'` / `'../../api/devices'`）。

- [ ] **Step 3: 实现**

创建 `frontend/src/api/settings.js`：

```js
import client from './client'

export function fetchInspectionInterval() {
  return client.get('/settings/inspection-interval')
}

export function updateInspectionInterval(minutes) {
  return client.put('/settings/inspection-interval', { poll_interval_minutes: minutes })
}
```

创建 `frontend/src/stores/settings.js`：

```js
import { defineStore } from 'pinia'
import { fetchInspectionInterval, updateInspectionInterval } from '../api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    pollIntervalMinutes: 5,
    loading: false,
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
  },
})
```

修改 `frontend/src/api/devices.js` 末尾追加：

```js
export function recheckAllDevices() {
  return client.post('/devices/recheck-all')
}
```

修改 `frontend/src/stores/devices.js`：第 2-8 行 import 列表加 `recheckAllDevices`，actions 里 `recheck` 之后追加：

```js
    async recheckAll() {
      await recheckAllDevices()
      await this.load()
    },
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/settings.spec.js src/stores/__tests__/devices.spec.js`
Expected: 3 passed（settings 2 + devices 1）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/devices.js frontend/src/stores/devices.js frontend/src/api/settings.js frontend/src/stores/settings.js frontend/src/stores/__tests__/settings.spec.js frontend/src/stores/__tests__/devices.spec.js
git commit -m "feat: add recheck-all action and settings store on frontend"
```

---

### Task 5: MainView 工具栏（立即巡检全部 + 间隔设置）

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Modify: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: `useDevicesStore().recheckAll()`、`useSettingsStore()`（`pollIntervalMinutes`、`loadInterval()`、`saveInterval(minutes)`）、`useAuthStore().user.role`（admin 判定）。
- Produces: 工具栏「立即巡检全部」按钮（所有人）+ admin 可见的数字输入（1~1440）与「保存」按钮。

- [ ] **Step 1: 写失败测试**

整体替换 `frontend/src/views/__tests__/MainView.spec.js`：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  createMock,
  loadMock,
  recheckAllMock,
  loadMeMock,
  logoutMock,
  pushMock,
  promptMock,
  successMock,
  errorMock,
  loadIntervalMock,
  saveIntervalMock,
} = vi.hoisted(() => ({
  createMock: vi.fn(),
  loadMock: vi.fn(),
  recheckAllMock: vi.fn(),
  loadMeMock: vi.fn(),
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
  promptMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  loadIntervalMock: vi.fn(),
  saveIntervalMock: vi.fn(),
}))

const authState = vi.hoisted(() => ({ role: 'admin' }))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: [],
    stats: { online: 0, offline: 0, warning: 0, unknown: 0 },
    load: loadMock,
    create: createMock,
    recheckAll: recheckAllMock,
  }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({
    user: { username: 'admin', role: authState.role },
    loadMe: loadMeMock,
    logout: logoutMock,
  }),
}))

vi.mock('../../stores/settings', () => ({
  useSettingsStore: () => ({
    pollIntervalMinutes: 5,
    loadInterval: loadIntervalMock,
    saveInterval: saveIntervalMock,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

import MainView from '../MainView.vue'

function mountView() {
  return mount(MainView, {
    global: {
      stubs: {
        DeviceTree: { template: '<div class="device-tree-stub" />' },
        'el-container': { template: '<div><slot /></div>' },
        'el-header': { template: '<header><slot /></header>' },
        'el-main': { template: '<main><slot /></main>' },
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-tree': { template: '<div><slot /></div>' },
        'el-input-number': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input class="interval-input" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
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

describe('MainView 新增根分组', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    promptMock.mockResolvedValue({ value: '研发部' })
  })

  it('点击后弹窗询问分组名，并以输入名称创建', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增根分组').trigger('click')
    expect(promptMock).toHaveBeenCalled()
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ name: '研发部', type: 'group' })
  })

  it('创建失败（如同名被拒）时提示后端错误，不静默失败', async () => {
    createMock.mockRejectedValue({ response: { data: { detail: '已存在同名节点' } } })
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增根分组').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('已存在同名节点')
  })
})

describe('MainView 自动刷新', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('挂载后每 30 秒自动调用 store.load()，卸载后停止', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(3)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(90000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(3)
  })
})

describe('MainView 立即巡检全部', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('点击按钮调用 store.recheckAll', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即巡检全部').trigger('click')
    await flushPromises()
    expect(recheckAllMock).toHaveBeenCalledTimes(1)
  })

  it('巡检全部失败时提示错误', async () => {
    recheckAllMock.mockRejectedValue({ response: { data: { detail: '巡检失败' } } })
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即巡检全部').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('巡检失败')
  })
})

describe('MainView 巡检间隔设置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载后 admin 加载当前间隔', async () => {
    authState.role = 'admin'
    mountView()
    await flushPromises()
    expect(loadIntervalMock).toHaveBeenCalledTimes(1)
  })

  it('保存间隔调用 saveInterval 并提示成功', async () => {
    authState.role = 'admin'
    saveIntervalMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '保存间隔').trigger('click')
    await flushPromises()
    expect(saveIntervalMock).toHaveBeenCalledWith(5)
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('viewer 不显示间隔设置控件，也不加载间隔', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存间隔')
    expect(loadIntervalMock).not.toHaveBeenCalled()
  })
})
```

注意：
- `authState.role` 在 `vi.hoisted` 定义，测试内改值再 `mountView()`；mock 工厂的 `useAuthStore` 每次调用返回 `user: { role: authState.role }`（mount 时取当前值）。各 describe 的 `beforeEach` 里 `vi.clearAllMocks()` 不影响 `authState.role`。
- 「自动刷新」用例中 `loadIntervalMock` 也会被调（admin 默认），不影响断言。
- 若「viewer」用例在「admin」用例之后运行，`authState.role` 已在测试内显式设回，互不影响。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: FAIL — 「立即巡检全部」按钮与「保存间隔」按钮不存在（模板未实现），断言 `.find(...)` 返回 undefined 后 `.trigger` 报错。

- [ ] **Step 3: 实现**

修改 `frontend/src/views/MainView.vue`：

`<script setup>` 顶部（第 6 行后）追加 import：

```js
import { useSettingsStore } from '../stores/settings'
```

第 11 行后追加：

```js
const settings = useSettingsStore()
```

`onMounted`（第 15-19 行）改为：

```js
onMounted(async () => {
  await auth.loadMe()
  await store.load()
  if (auth.user?.role === 'admin') {
    await settings.loadInterval()
  }
  refreshTimer = setInterval(() => store.load(), 30000)
})
```

新增函数（`onCreateRoot` 之后）：

```js
async function onRecheckAll() {
  try {
    await store.recheckAll()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '巡检失败')
  }
}

async function onSaveInterval() {
  try {
    await settings.saveInterval(settings.pollIntervalMinutes)
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}
```

模板工具栏（第 56-67 行）替换为：

```html
          <div class="toolbar">
            <el-button type="primary" @click="onCreateRoot">
              新增根分组
            </el-button>
            <el-button @click="store.load()">刷新</el-button>
            <el-button type="success" @click="onRecheckAll">立即巡检全部</el-button>
            <div v-if="auth.user?.role === 'admin'" class="interval-setting">
              <el-input-number
                v-model="settings.pollIntervalMinutes"
                :min="1"
                :max="1440"
                size="small"
              />
              <el-button size="small" @click="onSaveInterval">保存间隔</el-button>
            </div>
            <div class="stats">
              <el-tag type="success">在线 {{ store.stats.online }}</el-tag>
              <el-tag type="warning">警告 {{ store.stats.warning }}</el-tag>
              <el-tag type="danger">离线 {{ store.stats.offline }}</el-tag>
              <el-tag type="info">未知 {{ store.stats.unknown }}</el-tag>
            </div>
          </div>
```

`<style scoped>` 末尾追加：

```css
.interval-setting {
  display: flex;
  align-items: center;
  gap: 8px;
}
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: 8 passed（新增根分组 2 + 自动刷新 1 + 立即巡检全部 2 + 间隔设置 3）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: add recheck-all button and admin inspection interval setting to toolbar"
```

---

### Task 6: 全量回归 + 构建

- [ ] **Step 1: 后端回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 passed（49 个左右：38 原有 + settings 5 + scheduler 新增 3 + recheck 3）。

- [ ] **Step 2: 前端回归 + 构建**

Run（workdir=`frontend`）: `npm run test`
Expected: 全部 passed（9 原有 + settings 2 + devices 1 + MainView 新增 5 = 17）。

Run（workdir=`frontend`）: `npm run build`
Expected: `✓ built in ...`，仅有既存 chunk 大小警告。

- [ ] **Step 3: 提交任何遗漏**

若前面某步骤漏提交（`git status --short` 有未跟踪/修改），补提交。确认 `git log --oneline -6` 呈现本计划全部 5 个 feat 提交。

---

## Self-Review 备注

- **spec 覆盖**：recheck-all 接口 + 前端按钮 ✓（Task 3、4、5）；间隔设置界面/运行时/持久化/权限 ✓（Task 1、2、5）；校验 1~1440 ✓（Task 1 pydantic）；viewer 可触发巡检全部 ✓（Task 3）；admin 才能改间隔 ✓（Task 1）。
- **类型一致**：`collect_all_targets(db)` 定义于 Task 2、用于 Task 3，签名一致；`reschedule_interval(minutes)` 定义于 Task 1、用于 Task 2/3 测试，签名一致；`recheckAll()`/`saveInterval(minutes)`/`loadInterval()` 于 Task 4 定义、Task 5 消费。
- **APScheduler 已实测**：`reschedule_job("inspection", trigger=IntervalTrigger(minutes=3))` 在 3.10.4 下工作，`job.trigger.interval.seconds == 180`。
