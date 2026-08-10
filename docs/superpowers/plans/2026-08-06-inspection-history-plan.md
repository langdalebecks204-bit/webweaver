# 巡检历史记录 + 设备树横向滚动 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 Device 巡检历史记录（ProbeRecord）+ 历史查询 API + ECharts 单设备历史图表，并修复手机端设备树横向滚动。

**Architecture:** 后端新增 `ProbeRecord` 表，`run_inspection` 每次探测写入一条记录并在同事务清理过期记录；`GET /api/devices/{id}/history` 返回原始记录（升序），前端用 ECharts 按小时/天做平均聚合展示。设置 `probe_history_days`（默认 30）存 settings 表。前端 MainView 给 `el-tree` 外包横向滚动容器，DeviceTree 右键新增「查看历史」打开新组件 `DeviceHistory.vue`。

**Tech Stack:** Python FastAPI + SQLAlchemy + pytest；Vue3 + Element Plus + Pinia + Vitest(happy-dom) + ECharts。

## Global Constraints

- 后端测试基线全绿（现有 80 个），前端基线全绿（现有 38 个），`npm run build` 通过。
- 前端组件测试文件首行必须为 `// @vitest-environment happy-dom`。
- 提交前缀风格：`feat:`/`fix:`/`docs:`/`ci:`。
- 只记录 Device（设备树）历史；不记录 ExternalTarget；不做掉包率。
- 保留天数设置 `probe_history_days` 默认 30，合法范围 1-365。
- 历史 API 鉴权：GET 用 `get_current_user`；settings 的 GET/PUT 用 `require_admin`。
- `checked_at` 使用 `app.models.utcnow()`（naive UTC，与 Device.last_check 一致）。
- 数据库时间比较：清理与 days 过滤均用 `datetime.now(timezone.utc).replace(tzinfo=None)`。
- 前端 API 调用均经 `frontend/src/api/client.js`，`days` 参数默认 7（选项 1/7/30）。

---

### Task 1: 后端数据模型 + 历史查询 API + 测试

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py:8`
- Modify: `backend/app/routers/devices.py`
- Create: `backend/tests/test_history_api.py`
- Modify: `backend/tests/conftest.py:29-32`

**Interfaces:**
- Produces:
  - `class ProbeRecord` 在 `app.models`（字段 `id`、`device_id`(FK devices.id, ondelete CASCADE, index)、`checked_at`(DateTime, index)、`status`(str)、`latency_ms`(int|None)）。
  - `config.Settings.probe_history_days: int = 30`。
  - `GET /api/devices/{device_id}/history?days=7` → `{"device_id": int, "records": [{"checked_at": str, "status": str, "latency_ms": int|None}]}`，按 `checked_at` 升序。`days` 默认 7、`ge=1`。设备不存在返回 404。

- [ ] **Step 1: 写失败测试 `backend/tests/test_history_api.py`**

```python
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ProbeRecord, User
from app.security import hash_password


def _seed(device_id, checked_at, status="online", latency_ms=8):
    with SessionLocal() as db:
        db.add(ProbeRecord(device_id=device_id, checked_at=checked_at, status=status, latency_ms=latency_ms))
        db.commit()


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="histviewer", password_hash=hash_password("vp"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "histviewer", "password": "vp"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_history_returns_ascending_records(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    assert dev.status_code == 201
    dev_id = dev.json()["id"]
    old = _now() - timedelta(hours=2)
    _seed(dev_id, old)
    _seed(dev_id, _now(), status="offline", latency_ms=None)

    r = client.get(f"/api/devices/{dev_id}/history", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["device_id"] == dev_id
    assert [rec["status"] for rec in body["records"]] == ["online", "offline"]
    assert body["records"][0]["latency_ms"] == 8
    assert body["records"][1]["latency_ms"] is None
    assert body["records"][1]["checked_at"] >= body["records"][0]["checked_at"]


def test_history_days_filters_old(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    _seed(dev_id, _now() - timedelta(days=10))
    _seed(dev_id, _now())

    r = client.get(f"/api/devices/{dev_id}/history?days=1", headers=admin_headers)
    assert len(r.json()["records"]) == 1


def test_history_not_found(client, admin_headers):
    assert client.get("/api/devices/99999/history", headers=admin_headers).status_code == 404


def test_history_viewer_can_read(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    _seed(dev_id, _now())
    vh = _mk_viewer(client)
    assert client.get(f"/api/devices/{dev_id}/history", headers=vh).status_code == 200


def test_history_empty_records(client, admin_headers):
    dev = client.post("/api/devices", headers=admin_headers, json={"name": "sw", "type": "switch", "ip_address": "10.0.0.1"})
    dev_id = dev.json()["id"]
    r = client.get(f"/api/devices/{dev_id}/history", headers=admin_headers)
    assert r.json() == {"device_id": dev_id, "records": []}
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_history_api.py -v`
Expected: FAIL（`ImportError`/`ModuleNotFoundError: ProbeRecord`）

- [ ] **Step 3: 实现模型 + 配置 + 路由**

在 `backend/app/models.py` 中，`Setting` 类之后追加：

```python
class ProbeRecord(Base):
    __tablename__ = "probe_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

`backend/app/config.py` 在 `poll_interval_minutes` 后加一行：

```python
    probe_history_days: int = 30
```

`backend/app/database.py` 的 `init_db` 里 `from app.models import ...` 加入 `ProbeRecord`。

在 `backend/app/routers/devices.py` 顶部加 `from fastapi import Query`、`from datetime import datetime, timedelta, timezone`、`from app.models import ProbeRecord`，并添加路由（放在 `/{device_id}` GET 之后、`/{device_id}/recheck` 之前）：

```python
@router.get("/{device_id}/history")
def get_device_history(
    device_id: int,
    days: int = Query(default=7, ge=1),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    _get_or_404(db, device_id)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    records = db.scalars(
        select(ProbeRecord)
        .where(ProbeRecord.device_id == device_id, ProbeRecord.checked_at >= cutoff)
        .order_by(ProbeRecord.checked_at)
    ).all()
    return {
        "device_id": device_id,
        "records": [
            {
                "checked_at": r.checked_at.isoformat(),
                "status": r.status,
                "latency_ms": r.latency_ms,
            }
            for r in records
        ],
    }
```

- [ ] **Step 4: 更新 `conftest.py` 清理列表**

在 `backend/tests/conftest.py` 的 `clean_db` fixture 两处 `db.query(...).delete()` 区块中，`from app.models import Device, ExternalTarget, Setting, User` 改为：

```python
from app.models import Device, ExternalTarget, ProbeRecord, Setting, User
```

并在每组 delete 中加 `db.query(ProbeRecord).delete()`（放在 `Device` 之前，因 FK 依赖顺序）。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_history_api.py -v`
Expected: PASS（5 passed）

Run: `python -m pytest tests -v`
Expected: PASS（基线 80 + 新增 5 = 85 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/config.py backend/app/database.py backend/app/routers/devices.py backend/tests/test_history_api.py backend/tests/conftest.py
git commit -m "feat: add probe history model and query api"
```

---

### Task 2: 巡检写入记录 + 过期清理 + 测试

**Files:**
- Modify: `backend/app/inspector/engine.py:60-75`
- Modify: `backend/app/services/setting_service.py`
- Modify: `backend/tests/test_engine.py`
- Modify: `backend/app/routers/settings.py`

**Interfaces:**
- Consumes: `ProbeRecord`（Task 1）、`config.Settings.probe_history_days`。
- Produces:
  - `setting_service.get_probe_history_days(db) -> int`（读 settings 表 `probe_history_days`，缺省 config 值）。
  - `setting_service.set_probe_history_days(db, days: int) -> int`。
  - `PROBE_HISTORY_DAYS_KEY = "probe_history_days"` 常量。
  - `GET/PUT /api/settings/probe-history-days`（admin-only，PUT body `{"probe_history_days": int}` 范围 1-365）。
  - `run_inspection` 每设备探测后插入 ProbeRecord；巡检事务内清理过期记录。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_engine.py` 追加：

```python
from datetime import datetime, timedelta, timezone


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def test_run_inspection_writes_probe_record(monkeypatch, db):
    from app.models import ProbeRecord

    dev = Device(name="sw", type="switch", ip_address="10.0.0.1", port=22)
    db.add(dev)
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=8)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    await run_inspection(db, [dev])

    rec = db.query(ProbeRecord).filter(ProbeRecord.device_id == dev.id).one()
    assert rec.status == "online"
    assert rec.latency_ms == 8
    assert rec.checked_at is not None


async def test_run_inspection_cleans_old_records(monkeypatch, db):
    from app.models import ProbeRecord

    dev = Device(name="sw", type="switch", ip_address="10.0.0.1", port=22)
    db.add(dev)
    db.commit()
    old = _naive_now() - timedelta(days=100)
    db.add(ProbeRecord(device_id=dev.id, checked_at=old, status="offline", latency_ms=None))
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=5)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    await run_inspection(db, [dev])

    left = db.query(ProbeRecord).filter(ProbeRecord.device_id == dev.id).all()
    assert len(left) == 1
    assert left[0].status == "online"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_engine.py -k "probe_record or cleans_old" -v`
Expected: FAIL（断言失败：无 ProbeRecord 写入）

- [ ] **Step 3: 实现写入与清理**

`backend/app/services/setting_service.py` 追加（顶部 `from app.config import settings` 已存在）：

```python
PROBE_HISTORY_DAYS_KEY = "probe_history_days"


def get_probe_history_days(db: Session) -> int:
    row = db.get(Setting, PROBE_HISTORY_DAYS_KEY)
    if row is None:
        return settings.probe_history_days
    return int(row.value)


def set_probe_history_days(db: Session, days: int) -> int:
    row = db.get(Setting, PROBE_HISTORY_DAYS_KEY)
    if row is None:
        db.add(Setting(key=PROBE_HISTORY_DAYS_KEY, value=str(days)))
    else:
        row.value = str(days)
    db.commit()
    return days
```

`backend/app/inspector/engine.py` 顶部导入改为：

```python
from datetime import datetime, timedelta, timezone

from app.models import Device, ExternalTarget, ProbeRecord, utcnow
from app.services.device_service import device_to_dict
from app.services.external_service import external_target_to_dict
from app.services.setting_service import get_probe_history_days
```

`check_one` 内（更新 device 字段后、`return` 前）插入：

```python
        db.add(
            ProbeRecord(
                device_id=device.id,
                checked_at=device.last_check,
                status=result.status,
                latency_ms=result.latency_ms,
            )
        )
```

在 `run_inspection` 的 `db.commit()` 之前加清理（仅当有设备时执行）：

```python
    if devices:
        history_days = get_probe_history_days(db)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=history_days)
        db.query(ProbeRecord).filter(ProbeRecord.checked_at < cutoff).delete(synchronize_session=False)
    db.commit()
```

注意：`db.query(...).delete()` 会立即执行 SQL 并使其上的 `Device` 对象过期；`check_one` 里对 `device` 的字段赋值须在 `gather` 内完成（本实现已是）。清理放在 `results = await asyncio.gather(...)` 之后。

- [ ] **Step 4: 设置 API 测试与实现**

`backend/tests/test_settings_api.py` 追加：

```python
def test_probe_history_days_default(client, admin_headers):
    r = client.get("/api/settings/probe-history-days", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"probe_history_days": 30}


def test_probe_history_days_put_persists(client, admin_headers):
    r = client.put(
        "/api/settings/probe-history-days",
        headers=admin_headers,
        json={"probe_history_days": 60},
    )
    assert r.status_code == 200
    assert r.json() == {"probe_history_days": 60}

    got = client.get("/api/settings/probe-history-days", headers=admin_headers)
    assert got.json() == {"probe_history_days": 60}

    with SessionLocal() as db:
        row = db.get(Setting, "probe_history_days")
        assert row.value == "60"


def test_probe_history_days_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/settings/probe-history-days", headers=vh).status_code == 403
    assert client.put(
        "/api/settings/probe-history-days", headers=vh, json={"probe_history_days": 10}
    ).status_code == 403


def test_probe_history_days_out_of_range(client, admin_headers):
    assert client.put(
        "/api/settings/probe-history-days", headers=admin_headers, json={"probe_history_days": 0}
    ).status_code == 422
    assert client.put(
        "/api/settings/probe-history-days", headers=admin_headers, json={"probe_history_days": 366}
    ).status_code == 422
```

`backend/app/routers/settings.py` 顶部导入改为：

```python
from app.services.setting_service import (
    get_poll_interval,
    get_probe_history_days,
    set_poll_interval,
    set_probe_history_days,
)
```

追加 Pydantic 模型与路由：

```python
class ProbeHistoryDaysUpdate(BaseModel):
    probe_history_days: int = Field(ge=1, le=365)


@router.get("/probe-history-days")
def get_probe_history_days_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"probe_history_days": get_probe_history_days(db)}


@router.put("/probe-history-days")
def update_probe_history_days_route(
    payload: ProbeHistoryDaysUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    days = set_probe_history_days(db, payload.probe_history_days)
    return {"probe_history_days": days}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_engine.py -k "probe_record or cleans_old" tests/test_settings_api.py -v`
Expected: PASS

Run: `python -m pytest tests -v`
Expected: PASS（85 + 4 settings + 2 engine = 91 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/inspector/engine.py backend/app/services/setting_service.py backend/app/routers/settings.py backend/tests/test_engine.py backend/tests/test_settings_api.py
git commit -m "feat: record inspection history and enforce retention"
```

---

### Task 3: 前端依赖 + 横向滚动 + 历史入口

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/views/MainView.vue:176`
- Modify: `frontend/src/components/DeviceTree.vue`
- Modify: `frontend/src/components/__tests__/DeviceTree.spec.js`

**Interfaces:**
- Consumes: 现有 `store.tree`、`useDevicesStore`。
- Produces:
  - `DeviceTree.vue`：右键菜单「查看历史」（仅当 `props.node.ip_address` 非空）`command="history"`，emit 自定义事件 `open-history`（payload 为 node）。
  - `MainView.vue`：`el-tree` 外包 `<div class="tree-scroll">`，`v-if="historyDevice"` 挂 `<DeviceHistory :device="historyDevice" @close="historyDevice = null" />`（DeviceHistory 由 Task 4 创建）。
  - `frontend/package.json` 依赖含 `echarts`。

- [ ] **Step 1: 安装 echarts**

Run: `npm install echarts`（在 `frontend/` 目录，workdir=`frontend`）
Expected: `package.json` dependencies 出现 `"echarts": "^5.x.x"`，`npm run test` 仍通过基线。

- [ ] **Step 2: 写前端测试（历史入口）**

`frontend/src/components/__tests__/DeviceTree.spec.js` 追加用例（复用现有 `mountTree` 与 `defaultNode`，无需改 mock）：

```javascript
describe('DeviceTree 查看历史', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('带 IP 节点右键显示「查看历史」并发射 open-history', async () => {
    const wrapper = mountTree('history', defaultNode)
    await wrapper.find('.dd').trigger('click')
    const emitted = wrapper.emitted('open-history')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual(defaultNode)
  })

  it('不带 IP 的节点不发射 open-history', async () => {
    const wrapper = mountTree('history', { ...defaultNode, ip_address: null })
    await wrapper.find('.dd').trigger('click')
    expect(wrapper.emitted('open-history')).toBeFalsy()
  })
})
```

注意：测试 stub `el-dropdown` 只响应 `command` 入参；两个断言用 `mountTree('history', node)`，其中 node 有/无 `ip_address`。菜单项的「仅带 IP 显示」逻辑通过 `command` handler 内判断实现（见 Step 4），此测试即验证该判断。

- [ ] **Step 3: 运行确认失败**

Run: `npx vitest run src/components/__tests__/DeviceTree.spec.js`
Expected: FAIL（无 `open-history` 事件）

- [ ] **Step 4: 实现 DeviceTree 历史入口 + MainView 横向滚动**

`frontend/src/components/DeviceTree.vue`：

- `<script setup>` 中 `const emit = defineEmits(['open-history'])`。
- `onCommand` 加分支：

```javascript
  else if (command === 'history') {
    if (props.node.ip_address) emit('open-history', props.node)
  }
```

- 模板 dropdown 菜单（`add-sibling` 与 `edit` 之间）加：

```html
        <el-dropdown-item v-if="props.node.ip_address" command="history">查看历史</el-dropdown-item>
```

`frontend/src/views/MainView.vue`：

- `el-tree`（176 行起）外包 `<div class="tree-scroll">`（此步不改事件绑定，DeviceHistory 挂载在 Task 4 接入）：

```html
            <div class="tree-scroll">
              <el-tree ...>
                ...
              </el-tree>
            </div>
```

- `<style scoped>` 追加：

```css
.tree-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
}
.tree-scroll :deep(.el-tree) {
  min-width: max-content;
}
```

- [ ] **Step 5: 运行前端测试 + build**

Run: `npx vitest run src/components/__tests__/DeviceTree.spec.js`
Expected: PASS

Run: `npm run build`
Expected: PASS（本轮无 DeviceHistory 引用）

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/views/MainView.vue frontend/src/components/DeviceTree.vue frontend/src/components/__tests__/DeviceTree.spec.js
git commit -m "feat: add horizontal scroll and history menu entry"
```

---

### Task 4: 前端 DeviceHistory 图表组件 + 测试

**Files:**
- Create: `frontend/src/components/DeviceHistory.vue`
- Modify: `frontend/src/views/MainView.vue`
- Modify: `frontend/src/api/devices.js`
- Create: `frontend/src/components/__tests__/DeviceHistory.spec.js`

**Interfaces:**
- Consumes:
  - `fetchDeviceHistory(id, days)` → `Promise<{data: {device_id, records: [{checked_at, status, latency_ms}]}}>`。
  - props `device: {id, name}`，emit `close`。
- Produces: `DeviceHistory.vue` 组件（`el-dialog` 内含 ECharts 柱状图，粒度 hour/day、范围 1/7/30）。

- [ ] **Step 1: 实现 `frontend/src/api/devices.js` 历史函数**

在文件末尾追加：

```javascript
export function fetchDeviceHistory(id, days) {
  return client.get(`/devices/${id}/history`, { params: { days } })
}
```

- [ ] **Step 2: 接入 MainView（挂载 DeviceHistory + 事件绑定）**

`frontend/src/views/MainView.vue`：

- `<script setup>` 加 `const historyDevice = ref(null)`，import：

```javascript
import DeviceHistory from '../components/DeviceHistory.vue'
```

- `DeviceTree` 处加事件绑定：

```html
                <DeviceTree :node="data" @open-history="historyDevice = $event" />
```

- 在 `</el-tabs>` 之后（`targetDialogVisible` dialog 之前）加：

```html
      <DeviceHistory
        v-if="historyDevice"
        :device="historyDevice"
        @close="historyDevice = null"
      />
```

- [ ] **Step 3: 写失败测试 `frontend/src/components/__tests__/DeviceHistory.spec.js`**

```javascript
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { fetchMock, setOptionMock, resizeMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  setOptionMock: vi.fn(),
  resizeMock: vi.fn(),
}))

vi.mock('echarts', () => ({
  init: () => ({
    setOption: setOptionMock,
    resize: resizeMock,
    dispose: vi.fn(),
  }),
}))

vi.mock('../../api/devices', () => ({
  fetchDeviceHistory: fetchMock,
}))

import DeviceHistory from '../DeviceHistory.vue'

const device = { id: 1, name: 'sw' }

function mountComp(props = { device }) {
  return mount(DeviceHistory, {
    props,
    global: {
      stubs: {
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-radio-group': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="rg"><slot /></div>',
        },
        'el-radio-button': {
          props: ['value'],
          template: '<button class="rb"><slot /></button>',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><slot /></select>',
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

describe('DeviceHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMock.mockResolvedValue({
      data: {
        device_id: 1,
        records: [
          { checked_at: '2026-08-01T10:00:00', status: 'online', latency_ms: 8 },
          { checked_at: '2026-08-01T10:05:00', status: 'online', latency_ms: 12 },
          { checked_at: '2026-08-01T11:00:00', status: 'offline', latency_ms: null },
        ],
      },
    })
  })

  it('挂载后拉取历史并渲染柱状图（默认 7 天、hour 粒度）', async () => {
    mountComp()
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(1, 7)
    expect(setOptionMock).toHaveBeenCalled()
    const arg = setOptionMock.mock.calls[0][0]
    expect(arg.xAxis.data).toContain('2026-08-01 10:00')
    expect(arg.series[0].data).toContain(10)
  })

  it('切换范围重新拉取', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fetchMock.mockClear()
    await wrapper.find('select').setValue('30')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(1, 30)
  })
})
```

- [ ] **Step 4: 运行确认失败**

Run: `npx vitest run src/components/__tests__/DeviceHistory.spec.js`
Expected: FAIL（模块找不到 `../DeviceHistory.vue` 或断言不成立）

- [ ] **Step 5: 实现 `frontend/src/components/DeviceHistory.vue`**

```vue
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { fetchDeviceHistory } from '../api/devices'

const props = defineProps({ device: { type: Object, required: true } })
const emit = defineEmits(['close'])

const granularity = ref('hour')
const days = ref(7)
const chartEl = ref(null)
const records = ref([])
let chart = null

const chartOptions = computed(() => buildOptions(records.value, granularity.value))

function buildOptions(recs, gran) {
  const buckets = new Map()
  const keyOf = gran === 'day'
    ? (t) => `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
    : (t) => {
        const d = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
        return `${d} ${String(t.getHours()).padStart(2, '0')}:00`
      }
  for (const rec of recs) {
    if (rec.latency_ms == null) continue
    const key = keyOf(new Date(rec.checked_at))
    const b = buckets.get(key) || { sum: 0, count: 0 }
    b.sum += rec.latency_ms
    b.count += 1
    buckets.set(key, b)
  }
  const keys = [...buckets.keys()].sort()
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: keys, axisLabel: { rotate: 40 } },
    yAxis: { type: 'value', name: '平均延时(ms)' },
    series: [
      {
        type: 'bar',
        data: keys.map((k) => Math.round(buckets.get(k).sum / buckets.get(k).count)),
      },
    ],
  }
}

async function load() {
  const { data } = await fetchDeviceHistory(props.device.id, days.value)
  records.value = data.records
}

function renderChart() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(chartOptions.value, true)
}

function onResize() {
  if (chart) chart.resize()
}

watch(days, load)
watch(chartOptions, renderChart)

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="`历史延时 - ${props.device.name}`"
    width="720px"
    @close="emit('close')"
  >
    <div class="controls">
      <el-radio-group v-model="granularity">
        <el-radio-button value="hour">按小时</el-radio-button>
        <el-radio-button value="day">按天</el-radio-button>
      </el-radio-group>
      <el-select v-model="days" style="width: 120px">
        <el-option label="最近 1 天" :value="1" />
        <el-option label="最近 7 天" :value="7" />
        <el-option label="最近 30 天" :value="30" />
      </el-select>
    </div>
    <div ref="chartEl" class="chart" />
  </el-dialog>
</template>

<style scoped>
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}
.chart {
  width: 100%;
  height: 380px;
}
</style>
```

注意：`watch(days, load)` 仅 days 变化时重新拉取；粒度切换只改 `chartOptions`（computed 依赖 `granularity`），`watch(chartOptions, renderChart)` 自动重渲染，不重复请求。测试「切换范围重新拉取」断言 `fetchMock` 被以 `(1, 30)` 调用——`load()` 调用 `fetchDeviceHistory(props.device.id, days.value)`，满足。

- [ ] **Step 6: 运行前端测试 + 全量回归**

Run: `npx vitest run src/components/__tests__/DeviceHistory.spec.js`
Expected: PASS

Run: `npm run test`
Expected: PASS（38 + 新增 = 全绿）

Run: `npm run build`
Expected: PASS（DeviceHistory 已存在，MainView 引用解析成功）

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/DeviceHistory.vue frontend/src/components/__tests__/DeviceHistory.spec.js frontend/src/api/devices.js frontend/src/views/MainView.vue
git commit -m "feat: add device history chart component"
```

---

### Task 5: 全量回归 + 最终验收

**Files:**
- 无新文件；回归所有测试。

- [ ] **Step 1: 后端全量测试**

Run: `python -m pytest tests -v`（workdir=`backend`）
Expected: PASS（91 passed）

- [ ] **Step 2: 前端全量测试**

Run: `npm run test`（workdir=`frontend`）
Expected: PASS（全绿，含 DeviceHistory 新增用例）

- [ ] **Step 3: 前端 build**

Run: `npm run build`（workdir=`frontend`）
Expected: PASS，产出 `frontend/dist`。

- [ ] **Step 4: 手动冒烟（可选，若本地后端可启动）**

Run: `uvicorn app.main:app`（workdir=`backend`，加载 `frontend/dist`）
Expected: `/` 200、`/api/health` 200；右键带 IP 设备 →「查看历史」弹窗出图表。

- [ ] **Step 5: 提交最终状态**

```bash
git status --short
```

确认无遗漏改动后：
```bash
git log --oneline -6
```

（无新提交；前面 Task 已各自提交。）

- [ ] **Step 6: 验收标准核对（对照 spec）**

1. 手机端设备 Tab 横向滚动 ✔（Task 3 的 `.tree-scroll`）。
2. `GET /api/devices/{id}/history` 返回记录 ✔（Task 1）。
3. 右键「查看历史」弹 ECharts 柱状图、粒度/范围切换生效 ✔（Task 3+4）。
4. 超保留天数自动清理 ✔（Task 2）。
5. 删除设备级联删历史 ✔（Task 1 FK CASCADE + conftest 覆盖）。
6. 后端 pytest 全绿、前端 vitest 全绿、build 通过 ✔。
