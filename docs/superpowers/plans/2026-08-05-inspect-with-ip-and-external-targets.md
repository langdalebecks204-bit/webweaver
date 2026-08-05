# 带 IP 即巡检 + 外网目标检测 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复「分组类型带 IP 的设备不被巡检」问题（任何有 IP 的设备都巡检），并新增独立的外网目标列表（名称 + 可选 IP + 可选域名，IP 与域名分开检测、分开显示），纳入调度与「立即巡检全部」。

**Architecture:** 后端把巡检过滤条件改为仅 `ip_address 非空`；新增 `ExternalTarget` 模型 + `external_service` + `/api/external` CRUD 与 `check-all`；engine 新增 `run_external_inspection`（IP 用 `probe_device`，域名先 `asyncio.getaddrinfo` 解析再探测，结果分开存）；调度器同时跑设备与外网；`/devices/recheck-all` 返回 `{checked, external_checked}`。前端新增 `api/external.js` + `stores/external.js`，MainView 用 `el-tabs` 分「设备」「外网」，外网页签为表格 + CRUD 弹窗。

**Tech Stack:** FastAPI + SQLAlchemy + APScheduler + Pydantic（后端）；Vue 3 + Pinia + Element Plus + Vitest（前端）。

## Global Constraints

- 工作区：直接在主仓 `D:\code\WebWeaver`（用户选择不建 worktree），分支 `main`。
- 后端测试（workdir=backend）：`.venv\Scripts\python.exe -m pytest tests`，当前 49 passed。前端（workdir=frontend）：`npm run test`，当前 17 passed；构建 `npm run build`。
- 后端 fixture：`conftest.py` 的 `clean_db` 清空 `Device/Setting/User`；本计划需追加 `ExternalTarget` 清理。
- 外网目标权限：读/触发 `get_current_user`；写（增删改）`require_admin`。`/devices/recheck-all` 仍 `get_current_user`。
- 校验：`name` 非空（Field min_length=1）；`port` 1~65535；**IP 与域名至少填一个** → 422（service 层校验 `ValueError` → 422）。
- 无 IP 的设备（任何类型）仍不巡检；分组类型带 IP 的设备必须巡检。
- 无代码注释（除非必需）。提交信息以 `feat:`/`test:`/`fix:`/`docs:` 前缀开头。
- 前端测试用 Vitest + `@vue/test-utils` + `happy-dom`。组件测试文件首行 `// @vitest-environment happy-dom`；store 纯逻辑测试用 `node` 环境（不写该注释行）。

---

### Task 1: 修复巡检过滤（有 IP 即巡检）

**Files:**
- Modify: `backend/app/inspector/scheduler.py:11-16`（`collect_all_targets` 去掉 `type != "group"`）
- Modify: `backend/app/routers/devices.py:117-125`（`recheck_device` 去掉 `Device.type != "group"`）
- Modify: `backend/tests/test_scheduler.py:49-72`（更新期望）
- Modify: `backend/tests/test_devices_api.py`（追加 group+IP recheck 用例）

**Interfaces:**
- Consumes: 无。
- Produces: `collect_all_targets(db)` 返回所有 `ip_address 非空` 的设备（含分组）。

- [ ] **Step 1: 写失败测试**

修改 `backend/tests/test_scheduler.py` 的 `test_collect_all_targets_filters`（第 71 行断言）为：

```python
    with SessionLocal() as db:
        names = sorted(d.name for d in collect_all_targets(db))
        assert names == ["sub", "sw1", "sw2"]
```

（`sub` 是分组类型但带 IP，现在应被收集；`noip` 无 IP 仍排除。）

在 `backend/tests/test_devices_api.py` 末尾追加：

```python
def test_recheck_group_with_ip(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=3)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "g", "type": "group", "ip_address": "10.0.0.9"},
    ).json()
    r = client.post(f"/api/devices/{created['id']}/recheck", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["checked"][0]["status"] == "online"
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_scheduler.py::test_collect_all_targets_filters tests/test_devices_api.py::test_recheck_group_with_ip`
Expected: FAIL — `test_collect_all_targets_filters` 得 `["sw1","sw2"]` ≠ `["sub","sw1","sw2"]`；`test_recheck_group_with_ip` 的 `checked` 为空列表。

- [ ] **Step 3: 实现**

`backend/app/inspector/scheduler.py` 的 `collect_all_targets` 改为：

```python
def collect_all_targets(db) -> list[Device]:
    return list(
        db.scalars(
            select(Device).where(Device.ip_address.is_not(None))
        )
    )
```

`backend/app/routers/devices.py` 的 `recheck_device` 中查询条件改为：

```python
    targets = list(
        db.scalars(
            select(Device).where(
                Device.id.in_(ids),
                Device.ip_address.is_not(None),
            )
        )
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_scheduler.py tests/test_devices_api.py -v`
Expected: 全部 passed（scheduler 4 + devices_api 10）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/inspector/scheduler.py backend/app/routers/devices.py backend/tests/test_scheduler.py backend/tests/test_devices_api.py
git commit -m "fix: inspect every device with an IP regardless of type"
```

---

### Task 2: ExternalTarget 模型 + service + schema

**Files:**
- Modify: `backend/app/models.py`（追加 `ExternalTarget`）
- Create: `backend/app/services/external_service.py`
- Modify: `backend/app/schemas.py`（追加 ExternalTarget schema）
- Modify: `backend/app/database.py:35`（init_db import）
- Modify: `backend/tests/conftest.py`（clean_db 清 ExternalTarget）
- Create: `backend/tests/test_external_service.py`

**Interfaces:**
- Consumes: `app.models.utcnow`、`app.database.Base`、`app.schemas`。
- Produces: `ExternalTarget` 模型；`external_target_to_dict(t) -> dict`；`create_external_target(db, data)`（ValueError 当 IP/域名均空）；`update_external_target(db, id, data)`（KeyError 404、ValueError 422）；`delete_external_target(db, id) -> int`（KeyError 404）。Task 3/4 复用。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_external_service.py`：

```python
from app.database import SessionLocal
from app.models import ExternalTarget
from app.schemas import ExternalTargetCreate, ExternalTargetUpdate
from app.services.external_service import (
    create_external_target,
    delete_external_target,
    external_target_to_dict,
    update_external_target,
)


def test_create_and_dict():
    with SessionLocal() as db:
        t = create_external_target(
            db,
            ExternalTargetCreate(name="公网A", ip_address="8.8.8.8", domain="example.com"),
        )
        d = external_target_to_dict(t)
        assert d["name"] == "公网A"
        assert d["ip_address"] == "8.8.8.8"
        assert d["domain"] == "example.com"
        assert d["ip_status"] == "unknown"
        assert d["domain_status"] == "unknown"
        assert d["created_at"] is not None


def test_create_requires_target():
    with SessionLocal() as db:
        try:
            create_external_target(db, ExternalTargetCreate(name="x"))
            assert False, "should raise"
        except ValueError as exc:
            assert str(exc) == "ip_address or domain is required"


def test_update_and_delete():
    with SessionLocal() as db:
        t = create_external_target(db, ExternalTargetCreate(name="t", ip_address="1.1.1.1"))
        updated = update_external_target(
            db, t.id, ExternalTargetUpdate(name="t2", domain="x.com")
        )
        assert updated.name == "t2"
        assert updated.domain == "x.com"
        assert updated.ip_address == "1.1.1.1"

        try:
            update_external_target(db, t.id, ExternalTargetUpdate(ip_address=None, domain=None))
            assert False, "should raise"
        except ValueError:
            pass

        assert delete_external_target(db, t.id) == t.id
        assert db.get(ExternalTarget, t.id) is None


def test_update_missing_raises():
    with SessionLocal() as db:
        try:
            update_external_target(db, 9999, ExternalTargetUpdate(name="x"))
            assert False, "should raise"
        except KeyError:
            pass
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_external_service.py`
Expected: FAIL — `ImportError: cannot import name 'ExternalTarget'`。

- [ ] **Step 3: 实现**

`backend/app/models.py` 在 `Setting` 类后追加：

```python
class ExternalTarget(Base):
    __tablename__ = "external_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_status: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    ip_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    domain_status: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    domain_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
```

`backend/app/schemas.py` 末尾追加：

```python
class ExternalTargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip_address: str | None = None
    domain: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ExternalTargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip_address: str | None = None
    domain: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ExternalTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip_address: str | None
    domain: str | None
    port: int | None
    ip_status: str
    ip_latency_ms: int | None
    ip_last_check: datetime | None
    domain_status: str
    domain_latency_ms: int | None
    domain_last_check: datetime | None
    created_at: datetime
    updated_at: datetime
```

创建 `backend/app/services/external_service.py`：

```python
from sqlalchemy.orm import Session

from app.models import ExternalTarget
from app.schemas import ExternalTargetCreate, ExternalTargetUpdate


def external_target_to_dict(t: ExternalTarget) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "ip_address": t.ip_address,
        "domain": t.domain,
        "port": t.port,
        "ip_status": t.ip_status,
        "ip_latency_ms": t.ip_latency_ms,
        "ip_last_check": t.ip_last_check,
        "domain_status": t.domain_status,
        "domain_latency_ms": t.domain_latency_ms,
        "domain_last_check": t.domain_last_check,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def create_external_target(db: Session, data: ExternalTargetCreate) -> ExternalTarget:
    if not data.ip_address and not data.domain:
        raise ValueError("ip_address or domain is required")
    target = ExternalTarget(**data.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def update_external_target(
    db: Session, target_id: int, data: ExternalTargetUpdate
) -> ExternalTarget:
    target = db.get(ExternalTarget, target_id)
    if target is None:
        raise KeyError("target not found")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(target, key, value)
    if not target.ip_address and not target.domain:
        raise ValueError("ip_address or domain is required")
    db.commit()
    db.refresh(target)
    return target


def delete_external_target(db: Session, target_id: int) -> int:
    target = db.get(ExternalTarget, target_id)
    if target is None:
        raise KeyError("target not found")
    db.delete(target)
    db.commit()
    return target_id
```

`backend/app/database.py` 第 35 行改为：

```python
    from app.models import Device, ExternalTarget, Setting, User  # noqa: F401
```

`backend/tests/conftest.py`：第 21 行 import 改为：

```python
        from app.models import Device, ExternalTarget, Setting, User
```

并在两处 `db.query(Setting).delete()` 前各补一行：

```python
        db.query(ExternalTarget).delete()
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_external_service.py -v`
Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/app/schemas.py backend/app/services/external_service.py backend/app/database.py backend/tests/conftest.py backend/tests/test_external_service.py
git commit -m "feat: add ExternalTarget model and service"
```

---

### Task 3: 外网检测引擎 `run_external_inspection`

**Files:**
- Modify: `backend/app/inspector/engine.py`
- Modify: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `probe_device(ip, port, ping_timeout, tcp_timeout) -> ProbeResult`、`settings.ping_concurrency/ping_timeout/tcp_timeout`、`utcnow`、`external_target_to_dict(t)`。
- Produces: `run_external_inspection(db, targets) -> list[dict]`（并发 + 信号量；IP 探测写 `ip_*` 字段，域名解析+探测写 `domain_*` 字段；提交并返回 dict 列表）。Task 4/5 复用。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_engine.py` 末尾追加：

```python
async def test_run_external_inspection_updates_both(monkeypatch, db):
    import socket

    from app.inspector.engine import run_external_inspection
    from app.models import ExternalTarget

    target = ExternalTarget(name="t", ip_address="10.0.0.1", domain="example.com")
    db.add(target)
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=11)

    async def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    monkeypatch.setattr("asyncio.getaddrinfo", fake_getaddrinfo)

    results = await run_external_inspection(db, [target])
    assert results[0]["ip_status"] == "online"
    assert results[0]["ip_latency_ms"] == 11
    assert results[0]["domain_status"] == "online"
    assert results[0]["domain_latency_ms"] == 11
    assert target.ip_last_check is not None
    assert target.domain_last_check is not None


async def test_run_external_inspection_ip_only(monkeypatch, db):
    from app.inspector.engine import run_external_inspection
    from app.models import ExternalTarget

    target = ExternalTarget(name="t", ip_address="10.0.0.1")
    db.add(target)
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="warning", latency_ms=5)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    results = await run_external_inspection(db, [target])
    assert results[0]["ip_status"] == "warning"
    assert results[0]["domain_status"] == "unknown"
    assert target.ip_last_check is not None


async def test_run_external_inspection_domain_offline_on_resolve_fail(monkeypatch, db):
    import socket

    from app.inspector.engine import run_external_inspection
    from app.models import ExternalTarget

    target = ExternalTarget(name="t", domain="nope.invalid")
    db.add(target)
    db.commit()

    async def fake_getaddrinfo(host, port):
        raise socket.gaierror("no address")

    monkeypatch.setattr("asyncio.getaddrinfo", fake_getaddrinfo)

    results = await run_external_inspection(db, [target])
    assert results[0]["domain_status"] == "offline"
    assert results[0]["domain_latency_ms"] is None
    assert target.domain_last_check is not None
```

注意：`test_engine.py` 顶部已有 `import pytest`、`from app.inspector.engine import ... run_inspection`。三个新用例里 `import socket` 放在函数内即可；`asyncio` 由 `monkeypatch.setattr("asyncio.getaddrinfo", ...)` 直接引用模块名，无需在文件顶部 import（monkeypatch 按字符串解析）。若 linter 抱怨，可在函数内 `import asyncio`。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_engine.py -k "external" -v`
Expected: FAIL — `ImportError: cannot import name 'run_external_inspection'`。

- [ ] **Step 3: 实现**

修改 `backend/app/inspector/engine.py`：
- 第 13 行 import 改为：

```python
from app.models import Device, ExternalTarget, utcnow
from app.services.external_service import external_target_to_dict
```

- 在 `run_inspection`（文件末尾）之后追加：

```python
async def run_external_inspection(db, targets: list[ExternalTarget]) -> list[dict]:
    semaphore = asyncio.Semaphore(settings.ping_concurrency)

    async def resolve_domain(domain: str) -> str | None:
        try:
            infos = await asyncio.wait_for(
                asyncio.getaddrinfo(domain, None), timeout=settings.ping_timeout
            )
        except Exception:
            return None
        for info in infos:
            ip = info[4][0] if info[4] else None
            if ip:
                return ip
        return None

    async def check_one(target: ExternalTarget) -> dict:
        async with semaphore:
            if target.ip_address:
                result = await probe_device(
                    target.ip_address, target.port, settings.ping_timeout, settings.tcp_timeout
                )
                target.ip_status = result.status
                target.ip_latency_ms = result.latency_ms
                target.ip_last_check = utcnow()
            if target.domain:
                ip = await resolve_domain(target.domain)
                if ip is None:
                    target.domain_status = "offline"
                    target.domain_latency_ms = None
                else:
                    result = await probe_device(
                        ip, target.port, settings.ping_timeout, settings.tcp_timeout
                    )
                    target.domain_status = result.status
                    target.domain_latency_ms = result.latency_ms
                target.domain_last_check = utcnow()
        return external_target_to_dict(target)

    results = await asyncio.gather(*(check_one(t) for t in targets))
    db.commit()
    return list(results)
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_engine.py -v`
Expected: 全部 passed（原有 4 + 新增 3 = 7）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/inspector/engine.py backend/tests/test_engine.py
git commit -m "feat: add external target inspection engine"
```

---

### Task 4: 外网目标 API（CRUD + check-all）

**Files:**
- Create: `backend/app/routers/external.py`
- Modify: `backend/app/main.py`（注册路由）
- Create: `backend/tests/test_external_api.py`

**Interfaces:**
- Consumes: `create_external_target/update_external_target/delete_external_target/external_target_to_dict`（Task 2）、`run_external_inspection`（Task 3）、`get_current_user/require_admin`。
- Produces: `GET /api/external`、`POST /api/external`（201）、`PUT /api/external/{id}`、`DELETE /api/external/{id}`、`POST /api/external/check-all`。Task 5 复用 `check-all` 逻辑。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_external_api.py`：

```python
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _mk_viewer(client):
    with SessionLocal() as db:
        db.add(User(username="viewer1", password_hash=hash_password("viewpass"), role="viewer"))
        db.commit()
    r = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewpass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_list_update_delete(client, admin_headers):
    r = client.post("/api/external", headers=admin_headers,
                    json={"name": "公网", "ip_address": "8.8.8.8", "domain": "example.com"})
    assert r.status_code == 201
    target_id = r.json()["id"]
    assert r.json()["ip_status"] == "unknown"

    lst = client.get("/api/external", headers=admin_headers).json()
    assert len(lst) == 1
    assert lst[0]["domain"] == "example.com"

    up = client.put(f"/api/external/{target_id}", headers=admin_headers,
                    json={"name": "改名"})
    assert up.status_code == 200
    assert up.json()["name"] == "改名"

    d = client.delete(f"/api/external/{target_id}", headers=admin_headers)
    assert d.status_code == 200
    assert client.get("/api/external", headers=admin_headers).json() == []


def test_create_requires_target(client, admin_headers):
    r = client.post("/api/external", headers=admin_headers, json={"name": "x"})
    assert r.status_code == 422


def test_update_missing_404(client, admin_headers):
    r = client.put("/api/external/9999", headers=admin_headers, json={"name": "x"})
    assert r.status_code == 404


def test_external_admin_only_write(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/external", headers=vh).status_code == 200
    assert client.post("/api/external", headers=vh,
                       json={"name": "x", "ip_address": "1.1.1.1"}).status_code == 403
    assert client.delete("/api/external/1", headers=vh).status_code == 403


def test_check_all_updates_results(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=4)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    client.post("/api/external", headers=admin_headers,
                json={"name": "a", "ip_address": "8.8.8.8"})
    client.post("/api/external", headers=admin_headers,
                json={"name": "b", "domain": "example.com"})

    r = client.post("/api/external/check-all", headers=admin_headers)
    assert r.status_code == 200
    checked = r.json()["checked"]
    assert len(checked) == 2
    assert all(c["ip_status"] == "online" or c["domain_status"] == "online" for c in checked)
    assert all(c["ip_last_check"] is not None or c["domain_last_check"] is not None for c in checked)


def test_check_all_requires_auth(client):
    assert client.post("/api/external/check-all").status_code == 401
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_external_api.py`
Expected: FAIL — 404（路由未注册）。

- [ ] **Step 3: 实现**

创建 `backend/app/routers/external.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.inspector.engine import run_external_inspection
from app.models import ExternalTarget, User
from app.schemas import ExternalTargetCreate, ExternalTargetOut, ExternalTargetUpdate
from app.services.external_service import (
    create_external_target,
    delete_external_target,
    external_target_to_dict,
    update_external_target,
)

router = APIRouter()


@router.get("")
def list_external_targets(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return [
        external_target_to_dict(t)
        for t in db.scalars(select(ExternalTarget).order_by(ExternalTarget.id))
    ]


@router.post("/check-all")
async def check_all_external_targets(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    targets = list(db.scalars(select(ExternalTarget).order_by(ExternalTarget.id)))
    results = await run_external_inspection(db, targets)
    return {"checked": results}


@router.post("", response_model=ExternalTargetOut, status_code=201)
def create_target(
    payload: ExternalTargetCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        target = create_external_target(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return target


@router.put("/{target_id}", response_model=ExternalTargetOut)
def update_target(
    target_id: int,
    payload: ExternalTargetUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        target = update_external_target(db, target_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="External target not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return target


@router.delete("/{target_id}")
def delete_target(
    target_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        deleted = delete_external_target(db, target_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="External target not found")
    return {"deleted": deleted}
```

注意：`POST /check-all` 声明在 `PUT/DELETE /{target_id}` 之前，避免路径歧义。

`backend/app/main.py`：第 7 行改为：

```python
from app.routers import auth, devices, external, users
```

第 29 行后追加：

```python
app.include_router(external.router, prefix="/api/external", tags=["external"])
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_external_api.py -v`
Expected: 6 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/external.py backend/app/main.py backend/tests/test_external_api.py
git commit -m "feat: add external target CRUD and check-all API"
```

---

### Task 5: 调度整合（外网纳入调度与 recheck-all）

**Files:**
- Modify: `backend/app/inspector/scheduler.py`（`collect_external_targets` + `scheduled_inspection` 跑外网）
- Modify: `backend/app/routers/devices.py`（`recheck_all_devices` 返回 `external_checked`）
- Modify: `backend/tests/test_scheduler.py`（新增 collect_external_targets 用例）
- Modify: `backend/tests/test_devices_api.py`（更新 recheck-all 断言）

**Interfaces:**
- Consumes: `run_external_inspection`（Task 3）、`ExternalTarget`（Task 2）、`collect_all_targets`。
- Produces: `collect_external_targets(db) -> list[ExternalTarget]`；`scheduled_inspection` 同时巡检设备与外网；`POST /api/devices/recheck-all` 返回 `{"checked": [...], "external_checked": [...]}`。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_scheduler.py` 末尾追加：

```python
def test_collect_external_targets_returns_all():
    from app.database import SessionLocal
    from app.inspector.scheduler import collect_external_targets
    from app.models import ExternalTarget

    with SessionLocal() as db:
        db.add_all(
            [
                ExternalTarget(name="t1", ip_address="8.8.8.8"),
                ExternalTarget(name="t2", domain="example.com"),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        assert len(collect_external_targets(db)) == 2
```

修改 `backend/tests/test_devices_api.py` 的 `test_recheck_all_devices`：
- 追加一个分组类型带 IP 的设备：

```python
    client.post("/api/devices", headers=admin_headers,
                json={"name": "grpip", "type": "group", "ip_address": "10.0.0.9", "parent_id": root["id"]})
```

- 断言改为：

```python
    r = client.post("/api/devices/recheck-all", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["checked"]) == 3
    assert all(c["status"] == "online" for c in body["checked"])
    assert body["external_checked"] == []
```

- 并追加一个含外网目标时 recheck-all 的用例：

```python
def test_recheck_all_includes_external(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=6)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    client.post("/api/external", headers=admin_headers,
                json={"name": "ext", "domain": "example.com"})

    r = client.post("/api/devices/recheck-all", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] == []
    assert len(body["external_checked"]) == 1
    assert body["external_checked"][0]["domain_status"] == "online"
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests/test_scheduler.py tests/test_devices_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_external_targets'`；`test_recheck_all_devices` 断言 `external_checked` 键不存在、checked 数量不符。

- [ ] **Step 3: 实现**

`backend/app/inspector/scheduler.py`：第 5 行 import 改为：

```python
from app.models import Device, ExternalTarget
```

在 `collect_all_targets` 之后追加：

```python
def collect_external_targets(db) -> list[ExternalTarget]:
    return list(db.scalars(select(ExternalTarget)))
```

`scheduled_inspection` 改为：

```python
async def scheduled_inspection() -> None:
    from app.inspector.engine import run_external_inspection, run_inspection

    with SessionLocal() as db:
        devices = collect_all_targets(db)
        if devices:
            await run_inspection(db, devices)
        targets = collect_external_targets(db)
        if targets:
            await run_external_inspection(db, targets)
```

`backend/app/routers/devices.py`：
- 第 7 行 import 追加 `run_external_inspection`：

```python
from app.inspector.engine import run_external_inspection, run_inspection
```

- 第 8 行 import 追加 `collect_external_targets`：

```python
from app.inspector.scheduler import collect_all_targets, collect_external_targets
```

- `recheck_all_devices` 改为：

```python
@router.post("/recheck-all")
async def recheck_all_devices(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    targets = collect_all_targets(db)
    results = await run_inspection(db, targets)
    external = collect_external_targets(db)
    external_results = await run_external_inspection(db, external)
    return {"checked": results, "external_checked": external_results}
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 passed（49 原有 + external_service 4 + external_api 6 + engine 3 + scheduler 1 + devices_api 2 ≈ 65）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/inspector/scheduler.py backend/app/routers/devices.py backend/tests/test_scheduler.py backend/tests/test_devices_api.py
git commit -m "feat: include external targets in scheduler and recheck-all"
```

---

### Task 6: 前端 external API + store

**Files:**
- Create: `frontend/src/api/external.js`
- Create: `frontend/src/stores/external.js`
- Create: `frontend/src/stores/__tests__/external.spec.js`

**Interfaces:**
- Consumes: `frontend/src/api/client`。
- Produces: `fetchExternalTargets()`、`createExternalTarget(payload)`、`updateExternalTarget(id, payload)`、`deleteExternalTarget(id)`、`checkAllExternalTargets()`；`useExternalStore()`（state `targets/loading`，actions `load()/create()/update()/remove()/checkAll()`）。Task 7 复用全部。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/stores/__tests__/external.spec.js`：

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const {
  fetchMock,
  createMock,
  updateMock,
  removeMock,
  checkAllMock,
  loadMock,
} = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  checkAllMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/external', () => ({
  fetchExternalTargets: fetchMock,
  createExternalTarget: createMock,
  updateExternalTarget: updateMock,
  deleteExternalTarget: removeMock,
  checkAllExternalTargets: checkAllMock,
}))

import { useExternalStore } from '../external'

describe('external store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('load fetches targets', async () => {
    fetchMock.mockResolvedValue({ data: [{ id: 1, name: 't' }] })
    const store = useExternalStore()
    await store.load()
    expect(store.targets).toHaveLength(1)
  })

  it('create then reload', async () => {
    createMock.mockResolvedValue({ data: {} })
    const store = useExternalStore()
    store.load = loadMock
    await store.create({ name: 'x' })
    expect(createMock).toHaveBeenCalledWith({ name: 'x' })
    expect(loadMock).toHaveBeenCalledTimes(1)
  })

  it('checkAll then reload', async () => {
    checkAllMock.mockResolvedValue({})
    const store = useExternalStore()
    store.load = loadMock
    await store.checkAll()
    expect(checkAllMock).toHaveBeenCalled()
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/external.spec.js`
Expected: FAIL — `Cannot find module '../../api/external'`。

- [ ] **Step 3: 实现**

创建 `frontend/src/api/external.js`：

```js
import client from './client'

export function fetchExternalTargets() {
  return client.get('/external')
}

export function createExternalTarget(payload) {
  return client.post('/external', payload)
}

export function updateExternalTarget(id, payload) {
  return client.put(`/external/${id}`, payload)
}

export function deleteExternalTarget(id) {
  return client.delete(`/external/${id}`)
}

export function checkAllExternalTargets() {
  return client.post('/external/check-all')
}
```

创建 `frontend/src/stores/external.js`：

```js
import { defineStore } from 'pinia'
import {
  checkAllExternalTargets,
  createExternalTarget,
  deleteExternalTarget,
  fetchExternalTargets,
  updateExternalTarget,
} from '../api/external'

export const useExternalStore = defineStore('external', {
  state: () => ({
    targets: [],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.targets = (await fetchExternalTargets()).data
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createExternalTarget(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateExternalTarget(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteExternalTarget(id)
      await this.load()
    },
    async checkAll() {
      await checkAllExternalTargets()
      await this.load()
    },
  },
})
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/stores/__tests__/external.spec.js`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/external.js frontend/src/stores/external.js frontend/src/stores/__tests__/external.spec.js
git commit -m "feat: add external targets api and store on frontend"
```

---

### Task 7: MainView 设备/外网 Tab + 外网表格

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Modify: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: `useExternalStore()`（`targets/load/create/update/remove/checkAll`）、`useDevicesStore().recheckAll()`、`useSettingsStore()`、`useAuthStore().user.role`。
- Produces: `el-tabs`（设备/外网）；外网页签表格 + admin CRUD 弹窗；「立即巡检全部」同时触发设备与外网。

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
  confirmMock,
  extLoadMock,
  extCreateMock,
  extUpdateMock,
  extRemoveMock,
  extCheckAllMock,
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
  confirmMock: vi.fn(),
  extLoadMock: vi.fn(),
  extCreateMock: vi.fn(),
  extUpdateMock: vi.fn(),
  extRemoveMock: vi.fn(),
  extCheckAllMock: vi.fn(),
}))

const authState = vi.hoisted(() => ({ role: 'admin' }))

const extTargets = vi.hoisted(() => [
  { id: 1, name: '百度', ip_address: '8.8.8.8', domain: 'baidu.com', ip_status: 'online', ip_latency_ms: 10, domain_status: 'offline', domain_latency_ms: null },
])

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock, confirm: confirmMock },
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

vi.mock('../../stores/external', () => ({
  useExternalStore: () => ({
    targets: extTargets,
    load: extLoadMock,
    create: extCreateMock,
    update: extUpdateMock,
    remove: extRemoveMock,
    checkAll: extCheckAllMock,
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
        'el-tabs': { template: '<div class="tabs"><slot /></div>' },
        'el-tab-pane': { template: '<div><slot /></div>' },
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
        'el-input-number': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input class="interval-input" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
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

  it('挂载后每 30 秒自动刷新设备树，卸载后停止', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)
    expect(extLoadMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)
    expect(extLoadMock).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(90000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)
  })
})

describe('MainView 立即巡检全部', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('点击按钮同时触发设备与外网检测', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即巡检全部').trigger('click')
    await flushPromises()
    expect(recheckAllMock).toHaveBeenCalledTimes(1)
    expect(extCheckAllMock).toHaveBeenCalledTimes(1)
  })
})

describe('MainView 巡检间隔设置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示保存间隔并可保存', async () => {
    authState.role = 'admin'
    saveIntervalMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '保存间隔').trigger('click')
    await flushPromises()
    expect(saveIntervalMock).toHaveBeenCalledWith(5)
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('viewer 不显示间隔设置', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存间隔')
  })
})

describe('MainView 外网页签', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染外网目标表格', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('百度')
    expect(wrapper.text()).toContain('8.8.8.8')
    expect(wrapper.text()).toContain('baidu.com')
  })

  it('立即检测按钮触发 external.checkAll', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即检测').trigger('click')
    await flushPromises()
    expect(extCheckAllMock).toHaveBeenCalledTimes(1)
  })

  it('admin 新增外网目标并保存', async () => {
    authState.role = 'admin'
    extCreateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增外网目标').trigger('click')
    await wrapper.findAll('.dlg input.t-input').at(0).setValue('新目标')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(extCreateMock).toHaveBeenCalledWith({
      name: '新目标',
      ip_address: null,
      domain: null,
      port: null,
    })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('admin 删除外网目标需确认', async () => {
    authState.role = 'admin'
    confirmMock.mockResolvedValue()
    extRemoveMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(extRemoveMock).toHaveBeenCalledWith(1)
    expect(successMock).toHaveBeenCalledWith('已删除')
  })

  it('viewer 不显示新增与删除按钮', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('新增外网目标')
    expect(wrapper.text()).not.toContain('删除')
  })
})
```

注意：
- `extTargets` 在 `vi.hoisted` 定义，store mock 工厂每次 `useExternalStore()` 返回同一数组引用（测试只读断言，无需改动）。
- 外网弹窗 4 个输入框：名称、IP、域名（`el-input` stub class `t-input`）+ 端口（`el-input-number` stub class `interval-input`）。`findAll('.dlg input.t-input').at(0)` 取名称输入。
- viewer 用例必须在自己前把 `authState.role` 设回 admin（下一用例重新设），本文件中每次 `mountView` 前都显式设置了 `authState.role`。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: FAIL — 外网相关按钮/表格不存在（模板未实现 Tab 与外网面板）。

- [ ] **Step 3: 实现**

修改 `frontend/src/views/MainView.vue`：

`<script setup>` 顶部追加 import 与状态：

```js
import { computed, onMounted, onUnmounted, ref } from 'vue'
```

（原 `import { onMounted, onUnmounted } from 'vue'` 替换为上面这行。）

第 7 行后追加：

```js
import { useExternalStore } from '../stores/external'
```

第 13 行后追加：

```js
const external = useExternalStore()
const activeTab = ref('devices')
const targetDialogVisible = ref(false)
const targetEditing = ref(null)
const targetForm = ref({ name: '', ip_address: '', domain: '', port: null })
const isAdmin = computed(() => auth.user?.role === 'admin')
```

`onMounted` 改为：

```js
onMounted(async () => {
  await auth.loadMe()
  await store.load()
  await external.load()
  if (auth.user?.role === 'admin') {
    await settings.loadInterval()
  }
  refreshTimer = setInterval(() => {
    store.load()
    external.load()
  }, 30000)
})
```

`onRecheckAll` 改为：

```js
async function onRecheckAll() {
  try {
    await Promise.all([store.recheckAll(), external.checkAll()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '巡检失败')
  }
}
```

新增函数（`onSaveInterval` 之后）：

```js
function openCreateTarget() {
  targetEditing.value = null
  targetForm.value = { name: '', ip_address: '', domain: '', port: null }
  targetDialogVisible.value = true
}

function openEditTarget(t) {
  targetEditing.value = t
  targetForm.value = {
    name: t.name,
    ip_address: t.ip_address || '',
    domain: t.domain || '',
    port: t.port ?? null,
  }
  targetDialogVisible.value = true
}

async function onSaveTarget() {
  const payload = {
    name: targetForm.value.name,
    ip_address: targetForm.value.ip_address || null,
    domain: targetForm.value.domain || null,
    port: targetForm.value.port || null,
  }
  try {
    if (targetEditing.value) {
      await external.update(targetEditing.value.id, payload)
    } else {
      await external.create(payload)
    }
    targetDialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function onDeleteTarget(t) {
  try {
    await ElMessageBox.confirm(`确定删除外网目标「${t.name}」？`, '删除确认')
  } catch (error) {
    return
  }
  try {
    await external.remove(t.id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function onExternalCheckAll() {
  try {
    await external.checkAll()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检测失败')
  }
}
```

模板 `el-main` 内整体替换为：

```html
    <el-main>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="设备" name="devices">
          <el-card>
            <template #header>
              <div class="toolbar">
                <el-button type="primary" @click="onCreateRoot">
                  新增根分组
                </el-button>
                <el-button @click="store.load()">刷新</el-button>
                <el-button type="success" @click="onRecheckAll">立即巡检全部</el-button>
                <div v-if="isAdmin" class="interval-setting">
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
            </template>
            <el-tree
              :data="store.tree"
              :props="{ label: 'name', children: 'children' }"
              node-key="id"
              default-expand-all
              :expand-on-click-node="false"
            >
              <template #default="{ data }">
                <DeviceTree :node="data" />
              </template>
            </el-tree>
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="外网" name="external">
          <el-card>
            <template #header>
              <div class="toolbar">
                <el-button v-if="isAdmin" type="primary" @click="openCreateTarget">
                  新增外网目标
                </el-button>
                <el-button @click="external.load()">刷新</el-button>
                <el-button type="success" @click="onExternalCheckAll">立即检测</el-button>
              </div>
            </template>
            <table class="external-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>IP</th>
                  <th>IP 状态</th>
                  <th>IP 延时</th>
                  <th>域名</th>
                  <th>域名状态</th>
                  <th>域名延时</th>
                  <th v-if="isAdmin">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in external.targets" :key="t.id">
                  <td>{{ t.name }}</td>
                  <td>{{ t.ip_address || '-' }}</td>
                  <td>{{ t.ip_address ? t.ip_status : '-' }}</td>
                  <td>{{ t.ip_latency_ms != null ? t.ip_latency_ms + ' ms' : '-' }}</td>
                  <td>{{ t.domain || '-' }}</td>
                  <td>{{ t.domain ? t.domain_status : '-' }}</td>
                  <td>{{ t.domain_latency_ms != null ? t.domain_latency_ms + ' ms' : '-' }}</td>
                  <td v-if="isAdmin">
                    <el-button size="small" @click="openEditTarget(t)">编辑</el-button>
                    <el-button size="small" type="danger" @click="onDeleteTarget(t)">删除</el-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <el-dialog v-model="targetDialogVisible" :title="targetEditing ? '编辑外网目标' : '新增外网目标'">
        <el-form label-width="80px">
          <el-form-item label="名称">
            <el-input v-model="targetForm.name" />
          </el-form-item>
          <el-form-item label="IP 地址">
            <el-input v-model="targetForm.ip_address" placeholder="可选" />
          </el-form-item>
          <el-form-item label="域名">
            <el-input v-model="targetForm.domain" placeholder="可选" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="targetForm.port" :min="1" :max="65535" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="targetDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="onSaveTarget">保存</el-button>
        </template>
      </el-dialog>
    </el-main>
```

`<style scoped>` 追加：

```css
.external-table {
  width: 100%;
  border-collapse: collapse;
}
.external-table th,
.external-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  text-align: left;
}
.external-table th {
  color: #606266;
  font-weight: 600;
}
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: 14 passed（根分组 2 + 刷新 1 + 巡检全部 1 + 间隔 2 + 外网 5 = 11？实际：根分组 2、自动刷新 1、立即巡检全部 1、间隔设置 2、外网页签 5 → 11。以实际输出为准，全部 passed）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: add external targets tab to MainView"
```

---

### Task 8: 全量回归 + 构建

- [ ] **Step 1: 后端回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 passed（约 65 个）。

- [ ] **Step 2: 前端回归 + 构建**

Run（workdir=`frontend`）: `npm run test`
Expected: 全部 passed（17 原有 + external store 3 + MainView 新增 ≈ 31；以实际输出为准）。

Run（workdir=`frontend`）: `npm run build`
Expected: `✓ built in ...`，仅有既存 chunk 大小警告。

- [ ] **Step 3: 提交任何遗漏**

`git status --short` 确认无未提交改动。`git log --oneline -8` 确认本计划全部 7 个提交（fix 1 + feat 6）就位。

---

## Self-Review 备注

- **spec 覆盖**：带 IP 即巡检 ✓（Task 1）；ExternalTarget 模型与 CRUD ✓（Task 2/4）；IP/域名分开检测与结果字段 ✓（Task 3）；纳入调度与 recheck-all ✓（Task 5）；前端 Tab 与表格 ✓（Task 6/7）；校验 IP/域名至少一 422 ✓（Task 2/4）；权限写 admin 读 anyone ✓（Task 4）。
- **类型一致**：`run_external_inspection(db, targets)` 于 Task 3 定义、Task 4/5 复用；`external_target_to_dict(t)` 于 Task 2 定义、Task 3/4 复用；`collect_external_targets(db)` 于 Task 5 定义并用于 recheck-all；`useExternalStore()` 的 `load/create/update/remove/checkAll` 于 Task 6 定义、Task 7 消费。
- **已实测**：APScheduler `reschedule_job`（上轮已验）；`asyncio.getaddrinfo` monkeypatch 模式在 pytest-asyncio AUTO 模式下可用（test_engine 现有 async 测试同模式）。
- **注意**：`recheck_device` 单节点路径与 `collect_all_targets` 同时修复（Task 1）；`test_recheck_all_viewer_allowed` 现返回 `{"checked": [], "external_checked": []}`（原断言 `r.json() == {"checked": []}` 需同步更新——Task 5 Step 1 一并改）。
