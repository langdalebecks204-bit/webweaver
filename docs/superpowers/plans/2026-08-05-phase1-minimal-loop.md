# 织网 WebWeaver — Phase 1 最小闭环 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个本地可运行的最小闭环：登录 → 树状维护设备 → 手动/定时巡检 → 前端状态展示，使用 SQLite，无需 Docker/MySQL。

**Architecture:** 单个 FastAPI 进程承载 REST API + APScheduler（异步定时巡检）+ 手动 recheck 接口；SQLAlchemy 以 SQLite 建表（生产可切 MySQL）。前端 Vue 3 + Element Plus 的 `el-tree` 渲染嵌套树，自定义节点插槽显示状态圆点与右键菜单。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、PyJWT、bcrypt、ping3、APScheduler；Vue 3、Vite 5、Pinia、Element Plus、axios、vitest。

## Global Constraints

- 本机为 Windows，命令以 PowerShell 给出；Linux 将 `python`/`.venv\Scripts\` 换为 `python3`/`.venv/bin/` 即可。不要 `cd` 切换目录，改用工具的 `workdir`。
- 后端一律使用虚拟环境 `backend/.venv`；安装命令固定为 `.venv\Scripts\python.exe -m pip install ...`，测试命令固定为 `.venv\Scripts\python.exe -m pytest ...`。
- 环境变量前缀 `WEAVER_`；DB 默认 `sqlite:///./weaver.db`（dev）。本计划测试通过 `tests/conftest.py` 在导入 app 前改写环境变量指向临时 SQLite，并关闭调度器。
- 状态取值固定为：`unknown | online | warning | offline`。类型取值：`group | server | switch | terminal`。
- 角色：`admin` 可增删改设备；`viewer` 只读（可触发 recheck）。JWT 放在 `Authorization: Bearer <token>`。
- 用户要求不写代码注释（除非任务明确要求）。
- 每次 Task 结束必须提交 git，message 用 `feat:`/`test:`/`docs:` 前缀。
- 巡检任务不允许重叠：`coalesce=True, max_instances=1`。
- 所有测试共用一个临时 SQLite 文件，`conftest.py` 提供 autouse 的 `clean_db` fixture 在每次测试前后清空 `devices`/`users` 表保证隔离。

---

### Task 1: 后端脚手架（venv + 依赖 + 配置 + 数据库引擎）

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/.env.example`
- Create: `backend/pytest.ini`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_database.py`

**Interfaces:**
- Consumes: 无（本项目首任务）。
- Produces: `app.config.settings`（`db_url`, `jwt_secret`, `token_expire_minutes`, `poll_interval_minutes`, `ping_concurrency`, `ping_timeout`, `tcp_timeout`, `default_admin`, `default_admin_password`, `enable_scheduler`）；`app.database.Base`、`app.database.engine`、`app.database.SessionLocal`、`app.database.get_db()`。测试侧：`tests/conftest.py` 在导入 app 前设置 `WEAVER_*` 环境变量。

- [ ] **Step 1: 创建 venv**

```powershell
python -m venv backend\.venv
```

- [ ] **Step 2: 写入依赖文件**

`backend/requirements.txt`：

```text
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
pydantic==2.10.4
pydantic-settings==2.7.0
PyJWT==2.10.1
bcrypt==4.2.1
ping3==4.0.2
apscheduler==3.10.4
```

`backend/requirements-dev.txt`：

```text
-r requirements.txt
pytest==8.3.4
pytest-asyncio==0.25.0
httpx==0.28.1
```

- [ ] **Step 3: 安装依赖**

```powershell
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Expected: `Successfully installed ...`（无报错）。

- [ ] **Step 4: 写 .env.example / pytest.ini / .gitignore**

`backend/.env.example`：

```text
WEAVER_DB_URL=sqlite:///./weaver.db
WEAVER_JWT_SECRET=dev-secret-change-me
WEAVER_TOKEN_EXPIRE_MINUTES=480
WEAVER_POLL_INTERVAL_MINUTES=5
WEAVER_PING_CONCURRENCY=100
WEAVER_PING_TIMEOUT=1.0
WEAVER_TCP_TIMEOUT=2.0
WEAVER_DEFAULT_ADMIN=admin
WEAVER_DEFAULT_ADMIN_PASSWORD=admin123
WEAVER_ENABLE_SCHEDULER=true
```

`backend/pytest.ini`：

```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
```

`backend/.gitignore`：

```text
.venv/
__pycache__/
*.pyc
.env
*.db
.pytest_cache/
```

- [ ] **Step 5: 写测试（failing）**

`backend/tests/test_database.py`：

```python
def test_settings_loaded_from_env():
    from app.config import settings
    assert settings.db_url.startswith("sqlite")
    assert settings.poll_interval_minutes >= 1


def test_session_opens_and_commits():
    from app.database import SessionLocal
    from sqlalchemy import text

    with SessionLocal() as db:
        result = db.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

- [ ] **Step 6: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_database.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app'`。

- [ ] **Step 7: 写实现代码**

`backend/app/__init__.py`：空文件。

`backend/app/config.py`：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_url: str = "sqlite:///./weaver.db"
    jwt_secret: str = "dev-secret-change-me"
    token_expire_minutes: int = 480
    poll_interval_minutes: int = 5
    ping_concurrency: int = 100
    ping_timeout: float = 1.0
    tcp_timeout: float = 2.0
    default_admin: str = "admin"
    default_admin_password: str = "admin123"
    enable_scheduler: bool = True

    model_config = SettingsConfigDict(
        env_prefix="WEAVER_", env_file=".env", extra="ignore"
    )


settings = Settings()
```

`backend/app/database.py`：

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
engine = create_engine(settings.db_url, connect_args=_connect_args)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if settings.db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/tests/conftest.py`：

```python
import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), f"weaver_test_{os.getpid()}.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)

os.environ["WEAVER_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["WEAVER_ENABLE_SCHEDULER"] = "0"
os.environ["WEAVER_JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    from app.database import SessionLocal
    from app.models import Device, User

    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_headers(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

（`clean_db` 依赖 `app.models`，`client` 依赖 `app.main`——分别在 Task 2/5 创建；在此之前这两个 fixture 不会被任何测试引用。）

- [ ] **Step 8: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_database.py -v`
Expected: 2 passed。

- [ ] **Step 9: Commit**

```bash
git add backend
git commit -m "feat: scaffold backend venv, config, and database engine"
```

---

### Task 2: 数据模型 + 建表 + 默认管理员

**Files:**
- Create: `backend/app/models.py`
- Modify: `backend/app/database.py`（追加 `init_db()` / `seed_default_admin()`）
- Create: `backend/app/security.py`（最小版：哈希函数）
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.database.Base/SessionLocal`（Task 1）。
- Produces: `app.models.Device`（`id, parent_id, name, type, ip_address, port, status, latency_ms, last_check, order_index, created_at, updated_at`）；`app.models.User`（`id, username, password_hash, role, created_at`）；`app.models.utcnow()`；`app.database.init_db()`（建表 + 若缺默认 admin 则创建）；`app.security.hash_password/verify_password`。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_models.py`：

```python
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, init_db
from app.models import Device, User


def test_create_device_and_user():
    init_db()
    with SessionLocal() as db:
        db.add_all(
            [
                Device(name="root", type="group"),
                Device(name="sw1", type="switch", ip_address="10.0.0.1"),
                User(username="alice", password_hash="x", role="viewer"),
            ]
        )
        db.commit()
        assert db.query(Device).count() == 2
        assert db.query(User).filter(User.username == "alice").one().role == "viewer"


def test_username_unique():
    init_db()
    with SessionLocal() as db:
        db.add_all(
            [
                User(username="bob", password_hash="x", role="viewer"),
                User(username="bob", password_hash="y", role="admin"),
            ]
        )
        try:
            db.commit()
            raise AssertionError("expected IntegrityError")
        except IntegrityError:
            db.rollback()


def test_default_admin_seeded():
    init_db()
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == "admin").first()
        assert admin is not None
        assert admin.username == "admin"
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_models.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.models'`。

- [ ] **Step 3: 写实现**

`backend/app/models.py`：

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="group")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
```

`backend/app/security.py`：

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
```

`backend/app/database.py` 末尾追加：

```python
def init_db() -> None:
    from app.models import Device, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    seed_default_admin()


def seed_default_admin() -> None:
    from app.models import User
    from app.security import hash_password

    with SessionLocal() as db:
        exists = db.query(User).filter(User.username == settings.default_admin).first()
        if exists is None:
            db.add(
                User(
                    username=settings.default_admin,
                    password_hash=hash_password(settings.default_admin_password),
                    role="admin",
                )
            )
            db.commit()
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_models.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add Device/User models, init_db, and default admin seeding"
```

---

### Task 3: 认证原语（密码哈希 + JWT）

**Files:**
- Modify: `backend/app/security.py`（补全 JWT 函数）
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.config.settings`（`jwt_secret`, `token_expire_minutes`）。
- Produces: `app.security.create_access_token(user_id: int, username: str, role: str) -> str`；`app.security.decode_access_token(token: str) -> dict`。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_security.py`：

```python
import datetime

import jwt

from app.config import settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    token = create_access_token(1, "admin", "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"


def test_token_expiry():
    expired = jwt.encode(
        {
            "sub": "1",
            "username": "u",
            "role": "viewer",
            "exp": datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    try:
        decode_access_token(expired)
        raise AssertionError("expected expired token error")
    except jwt.ExpiredSignatureError:
        pass
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_security.py -v`
Expected: FAIL，`ImportError: cannot import name 'create_access_token'`。

- [ ] **Step 3: 补全实现**

`backend/app/security.py` 全量替换为：

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_security.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add password hashing and JWT auth primitives"
```

---

### Task 4: Pydantic schemas + 鉴权依赖

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/deps.py`

**Interfaces:**
- Consumes: `app.models.User`、`app.security.decode_access_token`、`app.database.get_db`。
- Produces: schemas `LoginRequest, TokenResponse, UserOut, DeviceBase, DeviceCreate, DeviceUpdate, DeviceOut`（含 `children`）；deps `get_current_user(credentials, db) -> User`、`require_admin(user) -> User`。

- [ ] **Step 1: 写实现（纯定义，由 Task 5/7 接口测试覆盖）**

`backend/app/schemas.py`：

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: datetime


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="group", pattern="^(group|server|switch|terminal)$")
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    order_index: int = 0


class DeviceCreate(DeviceBase):
    parent_id: int | None = None


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, pattern="^(group|server|switch|terminal)$")
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    parent_id: int | None = None
    order_index: int | None = None


class DeviceOut(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    status: str
    latency_ms: int | None
    last_check: datetime | None
    children: list["DeviceOut"] = []


DeviceOut.model_rebuild()
```

`backend/app/deps.py`：

```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user
```

- [ ] **Step 2: 冒烟验证**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -c "import app.schemas, app.deps; print('ok')"`
Expected: `ok`。

- [ ] **Step 3: Commit**

```bash
git add backend
git commit -m "feat: add pydantic schemas and auth dependencies"
```

---

### Task 5: 认证接口 + 最小 main 入口

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `app.schemas.*`、`app.security.*`、`app.deps.get_current_user`、`app.database.*`、`app.models.User`。
- Produces: `app.routers.auth.router`（`POST /api/auth/login`、`GET /api/auth/me`）；`app.main.app`（FastAPI，lifespan 内 `init_db()` + 条件启动调度器；当前仅挂载 auth 路由与 `/api/health`）。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_auth_api.py`：

```python
def test_login_ok(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_with_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"


def test_me_without_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.routers'`。

- [ ] **Step 3: 写实现**

`backend/app/routers/__init__.py`：空文件。

`backend/app/routers/auth.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
```

`backend/app/main.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if settings.enable_scheduler:
        from app.inspector.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown()


app = FastAPI(title="织网 WebWeaver", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

（`app.inspector.scheduler` 到 Task 10 才创建；本任务及后续任务的测试均以 `WEAVER_ENABLE_SCHEDULER=0` 运行，不会触发该导入。此阶段若手动以默认配置启动服务器会失败——属预期，服务器在 Task 10 之后方可运行。）

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add login/me endpoints and app entrypoint"
```

---

### Task 6: 设备服务层（树构建 + CRUD + 约束）

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/device_service.py`
- Create: `backend/tests/test_device_service.py`

**Interfaces:**
- Consumes: `app.models.Device`、`app.schemas.DeviceCreate/DeviceUpdate`。
- Produces:
  - `device_service.device_to_dict(d: Device) -> dict`
  - `device_service.build_tree(db) -> list[dict]`
  - `device_service.build_subtree(db, root_id) -> dict`
  - `device_service.get_descendant_ids(db, root_id) -> list[int]`
  - `device_service.create_device(db, data) -> Device`（`ValueError`：parent 不存在 / 同级重名）
  - `device_service.update_device(db, device_id, data) -> Device`（`ValueError`：自引用 / 成环 / parent 不存在 / 同级重名；`KeyError`：不存在）
  - `device_service.delete_device(db, device_id) -> list[int]`

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_device_service.py`：

```python
import pytest

from app.database import SessionLocal, init_db
from app.schemas import DeviceCreate, DeviceUpdate
from app.services.device_service import (
    build_subtree,
    build_tree,
    create_device,
    delete_device,
    get_descendant_ids,
    update_device,
)


@pytest.fixture()
def db():
    init_db()
    with SessionLocal() as session:
        yield session


def _create(db, name, type="group", parent_id=None, ip=None, order_index=0):
    return create_device(
        db,
        DeviceCreate(
            name=name, type=type, parent_id=parent_id, ip_address=ip, order_index=order_index
        ),
    )


def test_create_and_tree(db):
    root = _create(db, "总部", "group")
    sw = _create(db, "核心交换机", "switch", parent_id=root.id, ip="10.0.0.1")
    _create(db, "终端A", "terminal", parent_id=sw.id, ip="10.0.0.10")
    tree = build_tree(db)
    assert tree[0]["name"] == "总部"
    assert tree[0]["children"][0]["name"] == "核心交换机"
    assert tree[0]["children"][0]["children"][0]["name"] == "终端A"


def test_tree_order_by_order_index(db):
    root = _create(db, "root")
    _create(db, "B", parent_id=root.id, order_index=2)
    _create(db, "A", parent_id=root.id, order_index=1)
    names = [n["name"] for n in build_tree(db)[0]["children"]]
    assert names == ["A", "B"]


def test_duplicate_name_in_same_parent(db):
    root = _create(db, "root")
    _create(db, "dup", parent_id=root.id)
    with pytest.raises(ValueError):
        _create(db, "dup", parent_id=root.id)


def test_parent_not_found(db):
    with pytest.raises(ValueError):
        _create(db, "x", parent_id=9999)


def test_self_parent_rejected(db):
    root = _create(db, "root")
    with pytest.raises(ValueError):
        update_device(db, root.id, DeviceUpdate(parent_id=root.id))


def test_cycle_rejected(db):
    root = _create(db, "root")
    child = _create(db, "child", parent_id=root.id)
    with pytest.raises(ValueError):
        update_device(db, root.id, DeviceUpdate(parent_id=child.id))


def test_update_clear_ip(db):
    root = _create(db, "root")
    sw = _create(db, "sw", "switch", parent_id=root.id, ip="1.2.3.4")
    updated = update_device(db, sw.id, DeviceUpdate(ip_address=None))
    assert updated.ip_address is None


def test_delete_subtree(db):
    root = _create(db, "root")
    sw = _create(db, "sw", parent_id=root.id)
    leaf = _create(db, "leaf", parent_id=sw.id)
    ids = delete_device(db, root.id)
    assert set(ids) == {root.id, sw.id, leaf.id}
    assert build_tree(db) == []


def test_build_subtree(db):
    root = _create(db, "root")
    sw = _create(db, "sw", parent_id=root.id)
    leaf = _create(db, "leaf", parent_id=sw.id)
    sub = build_subtree(db, sw.id)
    assert sub["name"] == "sw"
    assert sub["children"][0]["name"] == "leaf"
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_device_service.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services'`。

- [ ] **Step 3: 写实现**

`backend/app/services/__init__.py`：空文件。

`backend/app/services/device_service.py`：

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device
from app.schemas import DeviceCreate, DeviceUpdate


def device_to_dict(d: Device) -> dict:
    return {
        "id": d.id,
        "parent_id": d.parent_id,
        "name": d.name,
        "type": d.type,
        "ip_address": d.ip_address,
        "port": d.port,
        "status": d.status,
        "latency_ms": d.latency_ms,
        "last_check": d.last_check,
        "order_index": d.order_index,
    }


def get_descendant_ids(db: Session, root_id: int) -> list[int]:
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        children = list(db.scalars(select(Device.id).where(Device.parent_id.in_(frontier))))
        ids.extend(children)
        frontier = children
    return ids


def _build(db: Session, nodes: list[Device]) -> list[dict]:
    by_parent: dict[int | None, list[Device]] = {}
    for d in nodes:
        by_parent.setdefault(d.parent_id, []).append(d)

    def node(d: Device) -> dict:
        item = device_to_dict(d)
        item["children"] = [node(c) for c in by_parent.get(d.id, [])]
        return item

    return [node(d) for d in by_parent.get(None, [])]


def build_tree(db: Session) -> list[dict]:
    devices = db.scalars(select(Device).order_by(Device.order_index, Device.id)).all()
    return _build(db, list(devices))


def build_subtree(db: Session, root_id: int) -> dict:
    ids = get_descendant_ids(db, root_id)
    devices = db.scalars(
        select(Device).where(Device.id.in_(ids)).order_by(Device.order_index, Device.id)
    ).all()
    tree = _build(db, list(devices))
    return next((t for t in tree if t["id"] == root_id), None)


def create_device(db: Session, data: DeviceCreate) -> Device:
    if data.parent_id is not None:
        parent = db.get(Device, data.parent_id)
        if parent is None:
            raise ValueError("parent device not found")
        dup = db.scalars(
            select(Device).where(Device.parent_id == data.parent_id, Device.name == data.name)
        ).first()
        if dup is not None:
            raise ValueError("device name already exists under this parent")
    device = Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def update_device(db: Session, device_id: int, data: DeviceUpdate) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise KeyError("device not found")

    changes = data.model_dump(exclude_unset=True)
    new_parent_id = changes.get("parent_id", device.parent_id)
    new_name = changes.get("name", device.name)

    if new_parent_id is not None:
        if new_parent_id == device_id:
            raise ValueError("parent cannot be self")
        parent = db.get(Device, new_parent_id)
        if parent is None:
            raise ValueError("parent device not found")
        if new_parent_id in get_descendant_ids(db, device_id):
            raise ValueError("cycle not allowed")

    dup = db.scalars(
        select(Device).where(
            Device.parent_id == new_parent_id,
            Device.name == new_name,
            Device.id != device_id,
        )
    ).first()
    if dup is not None:
        raise ValueError("device name already exists under this parent")

    for key, value in changes.items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device_id: int) -> list[int]:
    ids = get_descendant_ids(db, device_id)
    db.query(Device).where(Device.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return ids
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_device_service.py -v`
Expected: 10 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add device service with tree build and CRUD validation"
```

---

### Task 7: 设备接口（tree / list / CRUD）

**Files:**
- Create: `backend/app/routers/devices.py`
- Modify: `backend/app/main.py`（挂载 devices 路由）
- Create: `backend/tests/test_devices_api.py`

**Interfaces:**
- Consumes: `app.services.device_service.*`、`app.schemas.*`、`app.deps.get_current_user/require_admin`、`app.models.Device`。
- Produces: `app.routers.devices.router`（前缀 `/api/devices`）：`GET ""`、`GET "/tree"`、`GET "/{device_id}"`、`POST ""`（admin，201）、`PUT "/{device_id}"`（admin）、`DELETE "/{device_id}"`（admin）。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_devices_api.py`：

```python
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def _mk_viewer(username="viewer1", password="viewpass"):
    with SessionLocal() as db:
        db.add(User(username=username, password_hash=hash_password(password), role="viewer"))
        db.commit()


def _login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_tree_empty(client, admin_headers):
    r = client.get("/api/devices/tree", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_root_and_child(client, admin_headers):
    root = client.post(
        "/api/devices", headers=admin_headers, json={"name": "总部", "type": "group"}
    )
    assert root.status_code == 201
    root_id = root.json()["id"]

    sw = client.post(
        "/api/devices",
        headers=admin_headers,
        json={"name": "核心交换机", "type": "switch", "parent_id": root_id,
              "ip_address": "10.0.0.1", "port": 443},
    )
    assert sw.status_code == 201
    assert sw.json()["status"] == "unknown"

    tree = client.get("/api/devices/tree", headers=admin_headers).json()
    assert tree[0]["children"][0]["name"] == "核心交换机"


def test_list_and_filter(client, admin_headers):
    client.post("/api/devices", headers=admin_headers,
                json={"name": "A", "type": "switch", "ip_address": "10.0.0.1"})
    client.post("/api/devices", headers=admin_headers,
                json={"name": "B", "type": "group"})
    all_items = client.get("/api/devices", headers=admin_headers).json()
    assert len(all_items) == 2
    switches = client.get("/api/devices", headers=admin_headers,
                          params={"type": "switch"}).json()
    assert len(switches) == 1


def test_duplicate_name_conflict(client, admin_headers):
    client.post("/api/devices", headers=admin_headers, json={"name": "dup", "type": "group"})
    r = client.post("/api/devices", headers=admin_headers, json={"name": "dup", "type": "group"})
    assert r.status_code == 409


def test_get_and_update(client, admin_headers):
    created = client.post("/api/devices", headers=admin_headers,
                          json={"name": "S1", "type": "switch", "ip_address": "1.1.1.1"})
    cid = created.json()["id"]
    r = client.put(f"/api/devices/{cid}", headers=admin_headers,
                   json={"ip_address": "2.2.2.2"})
    assert r.status_code == 200
    assert r.json()["ip_address"] == "2.2.2.2"

    got = client.get(f"/api/devices/{cid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "S1"


def test_get_404(client, admin_headers):
    r = client.get("/api/devices/9999", headers=admin_headers)
    assert r.status_code == 404


def test_delete_cascade(client, admin_headers):
    root = client.post("/api/devices", headers=admin_headers,
                       json={"name": "root", "type": "group"})
    rid = root.json()["id"]
    child = client.post("/api/devices", headers=admin_headers,
                        json={"name": "child", "type": "group", "parent_id": rid})
    cid = child.json()["id"]
    r = client.delete(f"/api/devices/{rid}", headers=admin_headers)
    assert r.status_code == 200
    assert set(r.json()["deleted"]) == {rid, cid}
    assert client.get("/api/devices/tree", headers=admin_headers).json() == []


def test_viewer_forbidden_from_write(client, admin_headers):
    _mk_viewer()
    vh = _login(client, "viewer1", "viewpass")
    assert client.get("/api/devices/tree", headers=vh).status_code == 200
    assert client.post("/api/devices", headers=vh,
                       json={"name": "x", "type": "group"}).status_code == 403
    assert client.delete("/api/devices/9999", headers=vh).status_code == 403
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_devices_api.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.routers.devices'`。

- [ ] **Step 3: 写实现**

`backend/app/routers/devices.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Device
from app.schemas import DeviceCreate, DeviceUpdate
from app.services.device_service import (
    build_tree,
    create_device as create_device_service,
    delete_device as delete_device_service,
    device_to_dict,
    update_device as update_device_service,
)

router = APIRouter()


def _get_or_404(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("")
def list_devices(
    status: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    query = select(Device).order_by(Device.order_index, Device.id)
    if status:
        query = query.where(Device.status == status)
    if type:
        query = query.where(Device.type == type)
    return [device_to_dict(d) for d in db.scalars(query)]


@router.get("/tree")
def get_tree(db: Session = Depends(get_db), _: object = Depends(get_current_user)):
    return build_tree(db)


@router.get("/{device_id}")
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return device_to_dict(_get_or_404(db, device_id))


@router.post("", status_code=201)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    try:
        device = create_device_service(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return device_to_dict(device)


@router.put("/{device_id}")
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    try:
        device = update_device_service(db, device_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return device_to_dict(device)


@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    _get_or_404(db, device_id)
    deleted = delete_device_service(db, device_id)
    return {"deleted": deleted}
```

`backend/app/main.py` 中 `app.include_router(...)` 处改为：

```python
from app.routers import auth, devices

app = FastAPI(title="织网 WebWeaver", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_devices_api.py -v`
Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add device REST endpoints"
```

---

### Task 8: 用户管理接口 + main 全量挂载

**Files:**
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`（挂载 users 路由）
- Modify: `backend/tests/test_auth_api.py`（追加 health 与用户管理用例）

**Interfaces:**
- Consumes: `app.schemas.UserOut`、`app.deps.require_admin`、`app.security.hash_password`、`app.models.User`。
- Produces: `app.routers.users.router`（前缀 `/api/users`）：`GET ""`、`POST ""`、`PUT "/{user_id}"`、`DELETE "/{user_id}"`（禁止删自己）。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_auth_api.py` 末尾追加：

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_users_crud_and_self_delete_guard(client):
    h = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {h.json()['access_token']}"}

    created = client.post("/api/users", headers=headers,
                          json={"username": "u1", "password": "pw123456", "role": "viewer"})
    assert created.status_code == 200
    uid = created.json()["id"]

    listed = client.get("/api/users", headers=headers).json()
    assert {u["username"] for u in listed} >= {"admin", "u1"}

    updated = client.put(f"/api/users/{uid}", headers=headers, json={"role": "admin"})
    assert updated.status_code == 200
    assert updated.json()["role"] == "admin"

    me = client.get("/api/auth/me", headers=headers).json()
    denied = client.delete(f"/api/users/{me['id']}", headers=headers)
    assert denied.status_code == 409

    r = client.delete(f"/api/users/{uid}", headers=headers)
    assert r.status_code == 200
    assert "u1" not in {u["username"] for u in client.get("/api/users", headers=headers).json()}


def test_users_requires_admin(client):
    h = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {h.json()['access_token']}"}
    client.post("/api/users", headers=headers,
                json={"username": "vr_viewer", "password": "pw123456", "role": "viewer"})

    vh = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'vr_viewer', 'password': 'pw123456'}).json()['access_token']}"}
    assert client.get("/api/users", headers=vh).status_code == 403
    assert client.post("/api/users", headers=vh,
                       json={"username": "x", "password": "pw123456", "role": "viewer"}).status_code == 403
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v`
Expected: 新增用例 FAIL（`/api/users` 404、`/api/health` 404）。

- [ ] **Step 3: 写实现**

`backend/app/routers/users.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import UserOut
from app.security import hash_password

router = APIRouter()


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="viewer", pattern="^(admin|viewer)$")


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|viewer)$")


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.scalars(select(User).where(User.username == payload.username)).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="cannot delete yourself")
    db.delete(user)
    db.commit()
    return {"deleted": user.id}
```

`backend/app/main.py` 中 import 与 include_router 处改为：

```python
from app.routers import auth, devices, users

app = FastAPI(title="织网 WebWeaver", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
```

- [ ] **Step 4: 全量回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 PASS（auth 4 + models 3 + security 3 + database 2 + device_service 10 + devices_api 8 + auth_api 新增 3）。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add user management endpoints and full router mounting"
```

---

### Task 9: 巡检引擎（并发 Ping + TCP 探测）

**Files:**
- Create: `backend/app/inspector/__init__.py`
- Create: `backend/app/inspector/engine.py`
- Create: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `app.models.Device`、`app.config.settings`、`app.models.utcnow`、`app.services.device_service.device_to_dict`。
- Produces:
  - `engine.icmp_ping(host: str, timeout: float) -> int | None`
  - `engine.tcp_probe(host: str, port: int, timeout: float) -> bool`
  - `engine.probe_device(ip: str, port: int | None, ping_timeout: float, tcp_timeout: float) -> ProbeResult`（dataclass：`status: str`, `latency_ms: int | None`）
  - `engine.run_inspection(db, devices: list[Device]) -> list[dict]`

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_engine.py`：

```python
import pytest

from app.database import SessionLocal, init_db
from app.inspector.engine import ProbeResult, probe_device, run_inspection
from app.models import Device


@pytest.fixture()
def db():
    init_db()
    with SessionLocal() as session:
        yield session


async def test_probe_online(monkeypatch):
    async def fake_icmp(host, timeout):
        return 12

    async def fake_tcp(host, port, timeout):
        return True

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    monkeypatch.setattr("app.inspector.engine.tcp_probe", fake_tcp)
    result = await probe_device("10.0.0.1", 443, 1.0, 2.0)
    assert result == ProbeResult(status="online", latency_ms=12)


async def test_probe_warning_when_port_fails(monkeypatch):
    async def fake_icmp(host, timeout):
        return 12

    async def fake_tcp(host, port, timeout):
        return False

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    monkeypatch.setattr("app.inspector.engine.tcp_probe", fake_tcp)
    result = await probe_device("10.0.0.1", 443, 1.0, 2.0)
    assert result == ProbeResult(status="warning", latency_ms=12)


async def test_probe_offline_when_ping_times_out(monkeypatch):
    async def fake_icmp(host, timeout):
        return None

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    result = await probe_device("10.0.0.1", None, 1.0, 2.0)
    assert result == ProbeResult(status="offline", latency_ms=None)


async def test_run_inspection_updates_db(monkeypatch, db):
    dev = Device(name="sw", type="switch", ip_address="10.0.0.1", port=22)
    db.add(dev)
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=8)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    results = await run_inspection(db, [dev])
    assert results[0]["status"] == "online"
    assert results[0]["latency_ms"] == 8
    assert dev.last_check is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_engine.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.inspector'`。

- [ ] **Step 3: 写实现**

`backend/app/inspector/__init__.py`：空文件。

`backend/app/inspector/engine.py`：

```python
import asyncio
from dataclasses import dataclass

from ping3.asyncio import async_ping

from app.config import settings
from app.models import Device, utcnow
from app.services.device_service import device_to_dict


@dataclass
class ProbeResult:
    status: str
    latency_ms: int | None = None


async def icmp_ping(host: str, timeout: float) -> int | None:
    try:
        latency = await async_ping(host, timeout=timeout, unit="ms")
    except Exception:
        return None
    if latency is None or latency is False:
        return None
    return int(round(latency))


async def tcp_probe(host: str, port: int, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def probe_device(
    ip: str, port: int | None, ping_timeout: float, tcp_timeout: float
) -> ProbeResult:
    latency = await icmp_ping(ip, ping_timeout)
    if latency is None:
        return ProbeResult(status="offline")
    if port is not None:
        ok = await tcp_probe(ip, port, tcp_timeout)
        if not ok:
            return ProbeResult(status="warning", latency_ms=latency)
    return ProbeResult(status="online", latency_ms=latency)


async def run_inspection(db, devices: list[Device]) -> list[dict]:
    semaphore = asyncio.Semaphore(settings.ping_concurrency)

    async def check_one(device: Device) -> dict:
        async with semaphore:
            result = await probe_device(
                device.ip_address, device.port, settings.ping_timeout, settings.tcp_timeout
            )
        device.status = result.status
        device.latency_ms = result.latency_ms
        device.last_check = utcnow()
        return device_to_dict(device)

    results = await asyncio.gather(*(check_one(d) for d in devices))
    db.commit()
    return list(results)
```

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_engine.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add concurrent ping/tcp inspection engine"
```

---

### Task 10: 调度器 + recheck 接口 + 全量回归

**Files:**
- Create: `backend/app/inspector/scheduler.py`
- Modify: `backend/app/routers/devices.py`（追加 recheck 端点）
- Create: `backend/tests/test_scheduler.py`
- Modify: `backend/tests/test_devices_api.py`（追加 recheck 用例）

**Interfaces:**
- Consumes: `engine.run_inspection`、`device_service.get_descendant_ids`、`app.database.SessionLocal`、`app.config.settings`。
- Produces: `scheduler.create_scheduler() -> AsyncIOScheduler`（job id `inspection`）；`scheduler.scheduled_inspection() -> None`。

- [ ] **Step 1: 写测试（failing）**

`backend/tests/test_scheduler.py`：

```python
from app.inspector.scheduler import create_scheduler


def test_scheduler_has_inspection_job():
    scheduler = create_scheduler()
    try:
        job = scheduler.get_job("inspection")
        assert job is not None
        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        scheduler.shutdown(wait=False)
```

`backend/tests/test_devices_api.py` 末尾追加：

```python
def test_recheck_single_device(client, admin_headers, monkeypatch):
    from app.inspector.engine import ProbeResult

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=7)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)

    created = client.post(
        "/api/devices", headers=admin_headers,
        json={"name": "SW", "type": "switch", "ip_address": "10.0.0.1", "port": 22},
    )
    cid = created.json()["id"]
    r = client.post(f"/api/devices/{cid}/recheck", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["checked"][0]["status"] == "online"

    got = client.get(f"/api/devices/{cid}", headers=admin_headers).json()
    assert got["status"] == "online"
    assert got["latency_ms"] == 7
```

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests\test_scheduler.py tests\test_devices_api.py -v`
Expected: 新增用例 FAIL（`No module named 'app.inspector.scheduler'` / recheck 404）。

- [ ] **Step 3: 写实现**

`backend/app/inspector/scheduler.py`：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Device


async def scheduled_inspection() -> None:
    from app.inspector.engine import run_inspection

    with SessionLocal() as db:
        devices = list(
            db.scalars(
                select(Device).where(
                    Device.ip_address.is_not(None), Device.type != "group"
                )
            )
        )
        if devices:
            await run_inspection(db, devices)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_inspection,
        "interval",
        minutes=settings.poll_interval_minutes,
        id="inspection",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
```

`backend/app/routers/devices.py` 修改两处：

顶部 import 中 `from app.services.device_service import (...)` 块补充 `get_descendant_ids`，并新增：

```python
from app.inspector.engine import run_inspection
```

文件末尾追加：

```python
@router.post("/{device_id}/recheck")
async def recheck_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    _get_or_404(db, device_id)
    ids = get_descendant_ids(db, device_id)
    targets = list(
        db.scalars(
            select(Device).where(
                Device.id.in_(ids),
                Device.ip_address.is_not(None),
                Device.type != "group",
            )
        )
    )
    results = await run_inspection(db, targets)
    return {"checked": results}
```

- [ ] **Step 4: 全量回归**

Run（workdir=`backend`）: `.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部 PASS（新增 scheduler 1 + recheck 1）。

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add APScheduler inspection job and recheck endpoint"
```

---

### Task 11: 前端（脚手架 + 登录 + 设备树 + stores）

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/api/auth.js`
- Create: `frontend/src/api/devices.js`
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/stores/devices.js`
- Create: `frontend/src/stores/devicesHelpers.js`
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/MainView.vue`
- Create: `frontend/src/components/DeviceTree.vue`
- Create: `frontend/src/stores/__tests__/devicesHelpers.spec.js`

**Interfaces:**
- Consumes: `api/client`、`api/auth.*`、`api/devices.*`、router。
- Produces:
  - `api/client`（axios，baseURL `/api`，请求注入 Bearer，401 自动登出跳 `/login`）。
  - `stores/devicesHelpers.js`：`updateStatus(tree, nodeId, patch) -> tree`、`removeNode(tree, nodeId) -> tree`（纯函数）。
  - `stores/auth.js`：`token`、`user`、`login(username,password)`、`loadMe()`、`logout()`。
  - `stores/devices.js`：`tree`、`loading`、`lastUpdated`、`stats` getter、`load/create/update/remove/recheck/applyStatus`。
  - 视图：LoginView（登录表单）、MainView（工具栏 + 树 + 统计）、DeviceTree（节点内容 + 状态圆点 + 右键菜单 + 新增/编辑弹窗）。

- [ ] **Step 1: 写配置文件**

`frontend/package.json`：

```json
{
  "name": "webweaver-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.7.9",
    "element-plus": "^2.9.1",
    "pinia": "^2.3.0",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "vite": "^5.4.11",
    "vitest": "^2.1.8"
  }
}
```

`frontend/vite.config.js`：

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'node',
  },
})
```

`frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>织网 WebWeaver</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

`frontend/.gitignore`：

```text
node_modules/
dist/
```

- [ ] **Step 2: 安装依赖**

```powershell
npm install --prefix frontend
```

Expected: `added N packages`，无 error。

- [ ] **Step 3: 写 helper 测试（failing）**

`frontend/src/stores/__tests__/devicesHelpers.spec.js`：

```js
import { describe, it, expect } from 'vitest'
import { updateStatus, removeNode } from '../devicesHelpers'

const tree = [
  {
    id: 1,
    name: 'root',
    children: [
      { id: 2, name: 'sw', status: 'unknown', children: [] },
      { id: 3, name: 'pc', status: 'unknown', children: [] },
    ],
  },
]

describe('updateStatus', () => {
  it('updates a nested node without mutating input', () => {
    const next = updateStatus(tree, 2, { status: 'online', latencyMs: 5 })
    expect(next[0].children[0]).toMatchObject({ id: 2, status: 'online', latencyMs: 5 })
    expect(next[0].children[1].status).toBe('unknown')
    expect(tree[0].children[0].status).toBe('unknown')
  })
})

describe('removeNode', () => {
  it('removes a nested node', () => {
    const next = removeNode(tree, 3)
    expect(next[0].children.map((n) => n.id)).toEqual([2])
  })
})
```

- [ ] **Step 4: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test`
Expected: FAIL，`Cannot find module '../devicesHelpers'`。

- [ ] **Step 5: 写应用入口与 api/stores**

`frontend/src/main.js`：

```js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}
app.mount('#app')
```

`frontend/src/App.vue`：

```vue
<template>
  <router-view />
</template>
```

`frontend/src/router/index.js`：

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import MainView from '../views/MainView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: MainView },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) return { path: '/login' }
})

export default router
```

`frontend/src/api/client.js`：

```js
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default client
```

`frontend/src/api/auth.js`：

```js
import client from './client'

export function login(payload) {
  return client.post('/auth/login', payload)
}

export function fetchMe() {
  return client.get('/auth/me')
}
```

`frontend/src/api/devices.js`：

```js
import client from './client'

export function fetchTree() {
  return client.get('/devices/tree')
}

export function fetchDevices(params) {
  return client.get('/devices', { params })
}

export function createDevice(payload) {
  return client.post('/devices', payload)
}

export function updateDevice(id, payload) {
  return client.put(`/devices/${id}`, payload)
}

export function deleteDevice(id) {
  return client.delete(`/devices/${id}`)
}

export function recheckDevice(id) {
  return client.post(`/devices/${id}/recheck`)
}
```

`frontend/src/stores/devicesHelpers.js`：

```js
export function updateStatus(tree, nodeId, patch) {
  return tree.map((node) => {
    if (node.id === nodeId) return { ...node, ...patch }
    if (node.children && node.children.length) {
      return { ...node, children: updateStatus(node.children, nodeId, patch) }
    }
    return node
  })
}

export function removeNode(tree, nodeId) {
  const result = []
  for (const node of tree) {
    if (node.id === nodeId) continue
    if (node.children && node.children.length) {
      result.push({ ...node, children: removeNode(node.children, nodeId) })
    } else {
      result.push(node)
    }
  }
  return result
}
```

`frontend/src/stores/auth.js`：

```js
import { defineStore } from 'pinia'
import { login as apiLogin, fetchMe } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('weaver_token') || '',
    user: null,
  }),
  actions: {
    async login(username, password) {
      const { data } = await apiLogin({ username, password })
      this.token = data.access_token
      localStorage.setItem('weaver_token', data.access_token)
      this.user = (await fetchMe()).data
    },
    async loadMe() {
      if (this.token && !this.user) {
        this.user = (await fetchMe()).data
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('weaver_token')
    },
  },
})
```

`frontend/src/stores/devices.js`：

```js
import { defineStore } from 'pinia'
import {
  createDevice,
  deleteDevice,
  fetchTree,
  recheckDevice,
  updateDevice,
} from '../api/devices'
import { removeNode, updateStatus } from './devicesHelpers'

export const useDevicesStore = defineStore('devices', {
  state: () => ({
    tree: [],
    loading: false,
    lastUpdated: null,
  }),
  getters: {
    stats(state) {
      const counts = { online: 0, offline: 0, warning: 0, unknown: 0 }
      const walk = (nodes) => {
        for (const node of nodes) {
          counts[node.status] = (counts[node.status] || 0) + 1
          if (node.children && node.children.length) walk(node.children)
        }
      }
      walk(state.tree)
      return counts
    },
  },
  actions: {
    async load() {
      this.loading = true
      try {
        this.tree = (await fetchTree()).data
        this.lastUpdated = new Date()
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createDevice(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateDevice(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteDevice(id)
      await this.load()
    },
    async recheck(id) {
      await recheckDevice(id)
      await this.load()
    },
    applyStatus(nodeId, status, latencyMs, lastCheck) {
      this.tree = updateStatus(this.tree, nodeId, { status, latencyMs, lastCheck })
    },
  },
})
```

- [ ] **Step 6: 写视图组件**

`frontend/src/views/LoginView.vue`：

```vue
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)

async function onSubmit() {
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>织网 WebWeaver</h2>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="admin123" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f5f7fa;
}
.login-card {
  width: 360px;
}
.login-card h2 {
  text-align: center;
}
</style>
```

`frontend/src/components/DeviceTree.vue`：

```vue
<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDevicesStore } from '../stores/devices'

const props = defineProps({ node: { type: Object, required: true } })
const store = useDevicesStore()
const dialogVisible = ref(false)
const editing = ref(null)
const form = ref({ name: '', type: 'group', ip_address: '', port: null, parent_id: null })

function openCreate(parentId) {
  editing.value = null
  form.value = { name: '', type: 'group', ip_address: '', port: null, parent_id: parentId }
  dialogVisible.value = true
}

function openEdit() {
  editing.value = props.node
  form.value = {
    name: props.node.name,
    type: props.node.type,
    ip_address: props.node.ip_address || '',
    port: props.node.port,
    parent_id: props.node.parent_id,
  }
  dialogVisible.value = true
}

async function submit() {
  const payload = {
    ...form.value,
    ip_address: form.value.ip_address || null,
    port: form.value.port || null,
  }
  if (editing.value) {
    await store.update(editing.value.id, payload)
  } else {
    await store.create(payload)
  }
  dialogVisible.value = false
  ElMessage.success('已保存')
}

async function remove() {
  try {
    await ElMessageBox.confirm(
      `确定删除"${props.node.name}"及其全部子节点？`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await store.remove(props.node.id)
  ElMessage.success('已删除')
}

function onCommand(command) {
  if (command === 'add-child') openCreate(props.node.id)
  else if (command === 'add-sibling') openCreate(props.node.parent_id)
  else if (command === 'edit') openEdit()
  else if (command === 'delete') remove()
  else if (command === 'recheck') store.recheck(props.node.id)
}
</script>

<template>
  <el-dropdown trigger="contextmenu" @command="onCommand">
    <div class="node">
      <el-icon class="type-icon">
        <component
          :is="props.node.type === 'group' ? 'Folder'
            : props.node.type === 'switch' ? 'Connection' : 'Monitor'"
        />
      </el-icon>
      <span class="status-dot" :class="props.node.status" />
      <span class="node-name">{{ props.node.name }}</span>
      <span v-if="props.node.ip_address" class="node-meta">{{ props.node.ip_address }}</span>
      <span v-if="props.node.latency_ms != null" class="node-meta">
        {{ props.node.latency_ms }}ms
      </span>
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="add-child">添加子节点</el-dropdown-item>
        <el-dropdown-item command="add-sibling">添加同级</el-dropdown-item>
        <el-dropdown-item command="edit">编辑</el-dropdown-item>
        <el-dropdown-item command="recheck">立即巡检</el-dropdown-item>
        <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑节点' : '新增节点'" width="460px">
    <el-form label-width="90px">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.type" style="width: 100%">
          <el-option label="分组" value="group" />
          <el-option label="服务器" value="server" />
          <el-option label="交换机" value="switch" />
          <el-option label="终端" value="terminal" />
        </el-select>
      </el-form-item>
      <el-form-item label="IP 地址">
        <el-input v-model="form.ip_address" placeholder="留空表示纯分组节点" />
      </el-form-item>
      <el-form-item label="TCP 端口">
        <el-input-number v-model="form.port" :min="1" :max="65535" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.node {
  display: flex;
  align-items: center;
  gap: 6px;
}
.type-icon {
  color: #909399;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.online {
  background: #67c23a;
}
.status-dot.offline {
  background: #f56c6c;
}
.status-dot.warning {
  background: #e6a23c;
}
.status-dot.unknown {
  background: #909399;
}
.node-meta {
  color: #909399;
  font-size: 12px;
}
</style>
```

`frontend/src/views/MainView.vue`：

```vue
<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDevicesStore } from '../stores/devices'
import DeviceTree from '../components/DeviceTree.vue'

const router = useRouter()
const auth = useAuthStore()
const store = useDevicesStore()

onMounted(async () => {
  await auth.loadMe()
  await store.load()
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <span class="title">织网 WebWeaver</span>
      <span class="user-info">用户：{{ auth.user?.username }}（{{ auth.user?.role }}）</span>
      <el-button link @click="onLogout">退出登录</el-button>
    </el-header>
    <el-main>
      <el-card>
        <template #header>
          <div class="toolbar">
            <el-button type="primary" @click="store.create({ name: '新建分组', type: 'group' })">
              新增根分组
            </el-button>
            <el-button @click="store.load()">刷新</el-button>
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
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.title {
  font-weight: 600;
  font-size: 18px;
}
.user-info {
  margin-left: auto;
  color: #606266;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
</style>
```

- [ ] **Step 7: 测试 + 构建验证**

Run（workdir=`frontend`）: `npm run test`
Expected: 2 passed。

Run（workdir=`frontend`）: `npm run build`
Expected: `✓ built in ...`，无错误。

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat: add frontend with login, device tree, and stores"
```

---

### Task 12: 端到端验证 + README

**Files:**
- Create: `README.md`（仓库根）

**Interfaces:**
- 无新接口。验证 Phase 1 全部验收点并形成文档。

- [ ] **Step 1: 写 README**

`README.md`：

```markdown
# 织网 (WebWeaver)

树状结构自动化网络状态检测平台。后台定时/手动巡检设备（ICMP Ping + 可选 TCP 端口探测），前端以树形展示设备层级与实时状态。

当前为 **Phase 1 验证版**：登录 → 设备树维护 → 手动/定时巡检 → 状态展示，本地 SQLite 运行。

## 技术栈

- 后端：Python 3.12 / FastAPI / SQLAlchemy 2 / APScheduler / ping3 / PyJWT / bcrypt
- 前端：Vue 3 / Vite / Element Plus / Pinia / axios
- 数据库：开发 SQLite（SQLAlchemy 可切 MySQL，Phase 2 提供 Compose 部署）

## 快速开始（本地开发）

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env              # Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

默认管理员：`admin` / `admin123`（请在 `.env` 中修改 `WEAVER_DEFAULT_ADMIN_PASSWORD`）。

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，用默认账号登录。

## 巡检说明

- 调度器默认每 5 分钟巡检一次（`WEAVER_POLL_INTERVAL_MINUTES`）。
- 状态判定：Ping 成功 → `online`；Ping 成功但 TCP 端口失败 → `warning`；Ping 失败 → `offline`；未巡检 → `unknown`。
- 树中右键节点可：添加子节点 / 添加同级 / 编辑 / 立即巡检 / 删除。

## 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v

cd frontend
npm run test
```

## 环境变量（见 backend/.env.example）

| 变量 | 默认 | 说明 |
|---|---|---|
| WEAVER_DB_URL | sqlite:///./weaver.db | SQLAlchemy 连接串 |
| WEAVER_JWT_SECRET | dev-secret-change-me | JWT 签名密钥 |
| WEAVER_TOKEN_EXPIRE_MINUTES | 480 | token 有效期 |
| WEAVER_POLL_INTERVAL_MINUTES | 5 | 巡检周期（分钟） |
| WEAVER_PING_CONCURRENCY | 100 | 并发探测上限 |
| WEAVER_PING_TIMEOUT | 1.0 | ICMP 超时（秒） |
| WEAVER_TCP_TIMEOUT | 2.0 | TCP 探测超时（秒） |
| WEAVER_DEFAULT_ADMIN | admin | 首次启动的默认管理员 |
| WEAVER_DEFAULT_ADMIN_PASSWORD | admin123 | 默认管理员密码（生产必改） |
| WEAVER_ENABLE_SCHEDULER | true | 是否启用定时巡检 |

## 接口速览

- `POST /api/auth/login` 登录获取 JWT
- `GET /api/auth/me` 当前用户
- `GET /api/devices/tree` 设备树（嵌套 JSON）
- `GET|POST /api/devices` 列表 / 新建（admin）
- `PUT|DELETE /api/devices/{id}` 修改 / 删除（admin，级联删子树）
- `POST /api/devices/{id}/recheck` 立即巡检（含子树）
- `GET|POST|PUT|DELETE /api/users` 用户管理（admin）

## 后续（Phase 2）

WebSocket 实时状态推送、用户管理界面、Docker Compose + MySQL 部署、前端轮询兜底。
```

- [ ] **Step 2: 后端集成冒烟（真实巡检）**

启动后端（workdir=`backend`，后台）:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

- [ ] **Step 3: curl 验证核心流程**

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }

$body = '{"name":"测试分组","type":"group"}'
$root = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/devices -Headers $h -ContentType "application/json" -Body $body

$body2 = '{"name":"本机","type":"server","parent_id":' + $root.id + ',"ip_address":"127.0.0.1","port":8000}'
$dev = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/devices -Headers $h -ContentType "application/json" -Body $body2

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/devices/$($dev.id)/recheck" -Headers $h | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/devices/tree -Headers $h | ConvertTo-Json -Depth 5
```

Expected: recheck 返回 `checked[0].status == "online"`（本机 127.0.0.1 ping 通、8000 端口开放）；tree 返回嵌套结构。

- [ ] **Step 4: 停掉后台 uvicorn，浏览器手动验证**

1. 重新 `uvicorn app.main:app --reload --port 8000`（workdir=`backend`）+ `npm run dev`（workdir=`frontend`）。
2. 浏览器访问 http://localhost:5173 ，`admin/admin123` 登录。
3. 新增根分组 → 新增带 IP 的设备 → 右键"立即巡检" → 状态圆点变绿（在线）/ 红（离线）。
4. 编辑节点、删除节点（二次确认）可用。
5. 观察后端日志出现周期巡检记录（默认 5 分钟；可临时把 `WEAVER_POLL_INTERVAL_MINUTES` 设为 1 观察）。

- [ ] **Step 5: 最终回归 + 提交**

```powershell
# workdir=backend
.\.venv\Scripts\python.exe -m pytest tests -v
# workdir=frontend
npm run test
```

Expected: 后端全部 PASS、前端 2 passed。

```bash
git add README.md
git commit -m "docs: add README with dev run instructions"
```

---

## Self-Review 记录

**Spec 覆盖对照：**
- 登录/鉴权/角色 → Task 3/5/8；admin/viewer 权限在 Task 7 与 Task 8 测试覆盖。
- 设备 CRUD + 树 → Task 6/7。
- 邻接表、级联删除、成环校验、同级重名 → Task 6。
- 巡检引擎（并发 Ping+TCP、状态映射 unknown/online/warning/offline）→ Task 9。
- 定时调度（APScheduler、`coalesce=True, max_instances=1` 防重叠）→ Task 10。
- 手动 recheck（单设备含子树）→ Task 10。
- 前端树 + 状态圆点 + 右键菜单 + 统计 → Task 11。
- 默认 admin 种子、多用户角色模型 → Task 2/8。
- README/验收 → Task 12。

**本计划明确推迟到 Phase 2 的内容**（不在 Phase 1）：WebSocket 实时推送、用户管理前端界面、状态筛选下拉联动、Docker Compose/MySQL 部署、CORS（开发用 Vite 代理规避）。已在 spec §6/§7/§11 定义为后续阶段，并在 README 备注。

**占位符扫描：** 无 TBD/TODO 遗留。Task 5 的 `app/main.py` 在 Task 10 之前若手动启动服务器会因缺少 scheduler 模块报错，测试路径已通过 `WEAVER_ENABLE_SCHEDULER=0` 规避，且 Step 说明中已明确该前提。

**类型一致性：** `probe_device(ip, port, ping_timeout, tcp_timeout) -> ProbeResult(status, latency_ms)` 在 Task 9/10 与测试一致；`run_inspection(db, devices) -> list[dict]` 一致；`device_to_dict` 输出键 `id/parent_id/name/type/ip_address/port/status/latency_ms/last_check/order_index` 在 Task 6 定义并被 Task 7/9/10 复用；前端 `stores/devicesHelpers` 的 `updateStatus/removeNode` 签名与 vitest 测试一致。
