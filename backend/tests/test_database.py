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


def test_migrate_adds_device_columns_to_legacy_db():
    import os
    import sqlite3
    import tempfile

    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.orm import Session

    from app.database import _migrate_schema
    from app.models import Device

    path = os.path.join(tempfile.gettempdir(), f"migrate_{os.getpid()}.db")
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(20) NOT NULL,
            ip_address VARCHAR(45),
            port INTEGER,
            status VARCHAR(10) NOT NULL,
            latency_ms INTEGER,
            last_check DATETIME,
            order_index INTEGER NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        INSERT INTO devices (id, name, type, status, order_index, created_at, updated_at)
        VALUES (1, 'root', 'group', 'unknown', 0, '2026-01-01', '2026-01-01');
        """
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{path}")
    _migrate_schema(engine)

    cols = {c["name"] for c in inspect(engine).get_columns("devices")}
    assert "location" in cols
    assert "image_url" in cols
    assert "snmp_community" in cols
    assert "snmp_version" in cols
    assert "snmp_port" in cols

    with Session(engine) as db:
        rows = db.scalars(select(Device)).all()
        assert len(rows) == 1
        assert rows[0].name == "root"
        assert rows[0].location is None
        assert rows[0].image_url is None
