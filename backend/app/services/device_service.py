from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import timezone

from app.models import Device
from app.schemas import DeviceCreate, DeviceUpdate
from app.services.device_types import is_valid_type


_SWITCH_TYPES = {"switch", "unmanaged_switch"}


def _validate_port_fields(db: Session, data: dict, port_count: int | None) -> None:
    bindings = data.get("port_bindings")
    if not bindings:
        return
    for key, binding in bindings.items():
        if not key.isdigit():
            raise ValueError("port binding key must be numeric")
        port = int(key)
        if port_count is not None and (port < 1 or port > port_count):
            raise ValueError(f"port {port} out of range 1..{port_count}")
        if db.get(Device, binding["target_id"]) is None:
            raise ValueError(f"port binding target {binding['target_id']} not found")


def device_to_dict(d: Device) -> dict:
    return {
        "id": d.id,
        "parent_id": d.parent_id,
        "name": d.name,
        "type": d.type,
        "ip_address": d.ip_address,
        "port": d.port,
        "location": d.location,
        "image_url": d.image_url,
        "port_count": d.port_count,
        "uplink_port": d.uplink_port,
        "port_bindings": d.port_bindings,
        "snmp_community": d.snmp_community,
        "snmp_version": d.snmp_version,
        "snmp_port": d.snmp_port,
        "status": d.status,
        "latency_ms": d.latency_ms,
        "last_check": d.last_check.replace(tzinfo=timezone.utc).isoformat()
        if d.last_check else None,
        "order_index": d.order_index,
    }


def get_descendant_ids(db: Session, root_id: int) -> list[int]:
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        children = list(db.scalars(select(Device.id).where(Device.parent_id.in_(frontier))))
        ids.extend(children)
        frontier = children
    return ids


def _build(db: Session, nodes: list[Device]) -> list[dict]:
    by_parent: dict[int | None, list[Device]] = {}
    node_ids = {d.id for d in nodes}
    for d in nodes:
        by_parent.setdefault(d.parent_id, []).append(d)

    def node(d: Device) -> dict:
        item = device_to_dict(d)
        item["children"] = [node(c) for c in by_parent.get(d.id, [])]
        return item

    return [node(d) for d in nodes if d.parent_id is None or d.parent_id not in node_ids]


def build_tree(db: Session) -> list[dict]:
    devices = db.scalars(select(Device).order_by(Device.order_index, Device.id)).all()
    return _build(db, list(devices))


def build_subtree(db: Session, root_id: int) -> dict:
    ids = get_descendant_ids(db, root_id)
    devices = db.scalars(
        select(Device).where(Device.id.in_(ids)).order_by(Device.order_index, Device.id)
    ).all()
    tree = _build(db, list(devices))
    return next((t for t in tree if t["id"] == root_id), None)


def create_device(db: Session, data: DeviceCreate) -> Device:
    if not is_valid_type(db, data.type):
        raise ValueError(f"invalid device type: {data.type}")
    if data.parent_id is not None:
        parent = db.get(Device, data.parent_id)
        if parent is None:
            raise ValueError("parent device not found")
    dup = db.scalars(
        select(Device).where(Device.parent_id == data.parent_id, Device.name == data.name)
    ).first()
    if dup is not None:
        raise ValueError("device name already exists under this parent")
    payload = data.model_dump()
    if data.type in _SWITCH_TYPES:
        _validate_port_fields(db, payload, payload.get("port_count"))
    else:
        payload.pop("port_count", None)
        payload.pop("uplink_port", None)
        payload.pop("port_bindings", None)
    device = Device(**payload)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def update_device(db: Session, device_id: int, data: DeviceUpdate) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise KeyError("device not found")

    changes = data.model_dump(exclude_unset=True)
    if "type" in changes and not is_valid_type(db, changes["type"]):
        raise ValueError(f"invalid device type: {changes['type']}")
    if changes.get("type", device.type) in _SWITCH_TYPES:
        _validate_port_fields(db, changes, changes.get("port_count", device.port_count))
    else:
        changes.pop("port_count", None)
        changes.pop("uplink_port", None)
        changes.pop("port_bindings", None)
    new_parent_id = changes.get("parent_id", device.parent_id)
    new_name = changes.get("name", device.name)

    if new_parent_id is not None:
        if new_parent_id == device_id:
            raise ValueError("parent cannot be self")
        parent = db.get(Device, new_parent_id)
        if parent is None:
            raise ValueError("parent device not found")
        if new_parent_id in get_descendant_ids(db, device_id):
            raise ValueError("cycle not allowed")

    dup = db.scalars(
        select(Device).where(
            Device.parent_id == new_parent_id,
            Device.name == new_name,
            Device.id != device_id,
        )
    ).first()
    if dup is not None:
        raise ValueError("device name already exists under this parent")

    for key, value in changes.items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device_id: int) -> list[int]:
    ids = get_descendant_ids(db, device_id)
    objs = db.scalars(select(Device).where(Device.id.in_(ids))).all()
    for o in objs:
        db.expunge(o)
    db.query(Device).where(Device.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    from app.services.image_service import delete_image_file

    for did in ids:
        delete_image_file(did)
    return ids
