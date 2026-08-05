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
