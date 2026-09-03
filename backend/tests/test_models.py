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


def test_device_snmp_fields():
    init_db()
    with SessionLocal() as db:
        dev = Device(
            name="snmp_sw",
            type="switch",
            ip_address="172.16.2.26",
            snmp_community="public",
            snmp_version="v2c",
            snmp_port=161
        )
        db.add(dev)
        db.commit()
        saved = db.query(Device).filter_by(name="snmp_sw").first()
        assert saved.snmp_community == "public"
        assert saved.snmp_version == "v2c"
        assert saved.snmp_port == 161


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
