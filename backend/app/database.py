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


def init_db() -> None:
    from app.models import Device, Setting, User  # noqa: F401

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
