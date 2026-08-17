from app.database import SessionLocal
from app.models import Setting
from app.services import device_types as dt


def test_builtin_types_contains_new_ones():
    for t in ["camera", "nvr", "router", "firewall", "ap", "printer", "nas", "ups"]:
        assert t in dt.BUILTIN_TYPES


def test_unmanaged_switch_is_builtin():
    assert "unmanaged_switch" in dt.BUILTIN_TYPES


def test_custom_types_default_empty():
    with SessionLocal() as db:
        assert dt.get_custom_types(db) == []


def test_set_custom_types_persists():
    with SessionLocal() as db:
        dt.set_custom_types(db, ["printer2"])
        assert dt.get_custom_types(db) == ["printer2"]
        row = db.get(Setting, dt.CUSTOM_TYPES_KEY)
        assert row is not None
        assert "printer2" in row.value


def test_is_valid_type():
    with SessionLocal() as db:
        assert dt.is_valid_type(db, "group") is True
        assert dt.is_valid_type(db, "camera") is True
        assert dt.is_valid_type(db, "bogus") is False
        dt.set_custom_types(db, ["nas2"])
        assert dt.is_valid_type(db, "nas2") is True