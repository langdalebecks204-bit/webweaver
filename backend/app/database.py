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


def init_db() -> None:
    from app.models import Device, ExternalTarget, ProbeRecord, Setting, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_schema()
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
