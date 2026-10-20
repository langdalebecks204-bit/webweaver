import pytest
from sqlalchemy import create_engine, inspect
from app.database import Base, init_db
from app.models import Device

def test_device_is_virtual_field(tmp_path):
    test_db = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{test_db}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    dev_cols = [c["name"] for c in inspector.get_columns("devices")]
    assert "is_virtual" in dev_cols

def test_device_is_virtual_default(tmp_path):
    dev = Device(name="Test Device", type="switch")
    assert hasattr(dev, "is_virtual")
    # default before DB insert or set
    assert dev.is_virtual is False or dev.is_virtual is None
