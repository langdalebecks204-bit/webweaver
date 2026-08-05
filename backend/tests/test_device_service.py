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