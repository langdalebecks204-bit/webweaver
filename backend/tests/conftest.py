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
    from app.database import Base, SessionLocal, engine

    try:
        from app.models import Device, ExternalTarget, Setting, User
    except ImportError:
        yield
        return

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(ExternalTarget).delete()
        db.query(Setting).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(Device).delete()
        db.query(ExternalTarget).delete()
        db.query(Setting).delete()
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
