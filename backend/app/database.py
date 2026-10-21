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


_DEVICE_ADDED_COLUMNS = {
    "location": "VARCHAR(100)",
    "image_url": "VARCHAR(255)",
    "port_count": "INTEGER",
    "uplink_port": "INTEGER",
    "port_bindings": "TEXT",
    "snmp_enabled": "BOOLEAN DEFAULT 1",
    "snmp_community": "VARCHAR(50)",
    "snmp_version": "VARCHAR(10)",
    "snmp_port": "INTEGER",
    "mac_address": "VARCHAR(50)",
    "is_virtual": "BOOLEAN NOT NULL DEFAULT 0",
}


def _migrate_schema(db_engine=None) -> None:
    from sqlalchemy import inspect, text

    db_engine = db_engine or engine
    inspector = inspect(db_engine)
    if not inspector.has_table("devices"):
        return
    existing = {col["name"] for col in inspector.get_columns("devices")}
    with db_engine.begin() as conn:
        for name, ddl in _DEVICE_ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE devices ADD COLUMN {name} {ddl}"))


def _migrate_terminal_names(db_engine=None) -> None:
    """Migrate legacy '终端 (未知厂商)' terminal names to include the MAC address."""
    from sqlalchemy import inspect, text

    db_engine = db_engine or engine
    inspector = inspect(db_engine)
    if not inspector.has_table("devices"):
        return
    with db_engine.begin() as conn:
        try:
            rows = conn.execute(
                text("SELECT id, name, mac_address FROM devices WHERE mac_address IS NOT NULL AND name LIKE '终端 (%未知厂商%)'")
            ).fetchall()
            for r in rows:
                dev_id, old_name, mac = r[0], r[1], r[2]
                if mac and "未知厂商" in old_name and mac not in old_name:
                    new_name = f"终端 (未知厂商{mac})"
                    conn.execute(
                        text("UPDATE devices SET name = :new_name WHERE id = :dev_id"),
                        {"new_name": new_name, "dev_id": dev_id},
                    )
        except Exception:
            pass


def init_db() -> None:
    from app.models import Device, ExternalTarget, ProbeRecord, Setting, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _migrate_terminal_names()
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
