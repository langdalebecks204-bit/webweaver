from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import seed_default_admin
from app.models import Device, ExternalTarget, Setting, User, utcnow

BACKUP_VERSION = 1
_VALID_TYPES = {"group", "server", "switch", "terminal"}


def export_backup(
    db: Session,
    include_devices: bool = True,
    include_external: bool = True,
    include_settings: bool = True,
) -> dict:
    data = {"version": BACKUP_VERSION, "exported_at": utcnow().isoformat()}
    if include_devices:
        devices = list(db.scalars(select(Device).order_by(Device.order_index, Device.id)))
        data["devices"] = _flatten_devices(devices)
    if include_external:
        targets = db.scalars(select(ExternalTarget).order_by(ExternalTarget.id)).all()
        data["external"] = [
            {"name": t.name, "ip_address": t.ip_address, "domain": t.domain, "port": t.port}
            for t in targets
        ]
    if include_settings:
        rows = db.scalars(select(Setting).order_by(Setting.key)).all()
        data["settings"] = [{"key": r.key, "value": r.value} for r in rows]
    return data


def _flatten_devices(devices: list[Device]) -> list[dict]:
    by_parent: dict[int | None, list[Device]] = {}
    node_ids = {d.id for d in devices}
    for d in devices:
        by_parent.setdefault(d.parent_id, []).append(d)
    out: list[dict] = []

    def walk(d: Device) -> None:
        out.append(
            {
                "id": d.id,
                "name": d.name,
                "type": d.type,
                "ip_address": d.ip_address,
                "port": d.port,
                "order_index": d.order_index,
                "parent_id": d.parent_id,
            }
        )
        for child in sorted(by_parent.get(d.id, []), key=lambda x: (x.order_index, x.id)):
            walk(child)

    for d in sorted(devices, key=lambda x: (x.order_index, x.id)):
        if d.parent_id is None or d.parent_id not in node_ids:
            walk(d)
    return out


def import_backup(db: Session, data, mode: str) -> None:
    if not isinstance(data, dict) or data.get("version") != BACKUP_VERSION:
        raise ValueError("unsupported backup version")
    if mode == "replace":
        _import_replace(db, data)
    else:
        _import_merge(db, data)
    db.commit()


def _import_replace(db: Session, data) -> None:
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    _import_devices(db, data.get("devices", []), merge=False)
    _import_external(db, data.get("external", []), merge=False)
    _import_settings(db, data.get("settings", []))


def _import_merge(db: Session, data) -> None:
    _import_devices(db, data.get("devices", []), merge=True)
    _import_external(db, data.get("external", []), merge=True)
    _import_settings(db, data.get("settings", []))


def _import_devices(db: Session, items, merge: bool) -> None:
    id_map: dict[int, int] = {}
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("device name is required")
        dev_type = item.get("type") or "group"
        if dev_type not in _VALID_TYPES:
            raise ValueError(f"invalid device type: {dev_type}")
        parent_id = id_map.get(item.get("parent_id"))
        if merge:
            existing = db.scalars(
                select(Device).where(Device.parent_id == parent_id, Device.name == name)
            ).first()
            if existing is not None:
                id_map[item["id"]] = existing.id
                continue
        device = Device(
            name=name,
            type=dev_type,
            ip_address=item.get("ip_address"),
            port=item.get("port"),
            order_index=item.get("order_index") or 0,
            parent_id=parent_id,
        )
        db.add(device)
        db.flush()
        id_map[item["id"]] = device.id


def _import_external(db: Session, items, merge: bool) -> None:
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("external target name is required")
        if not item.get("ip_address") and not item.get("domain"):
            raise ValueError("ip_address or domain is required")
        if merge:
            existing = db.scalars(
                select(ExternalTarget).where(ExternalTarget.name == name)
            ).first()
            if existing is not None:
                continue
        db.add(
            ExternalTarget(
                name=name,
                ip_address=item.get("ip_address"),
                domain=item.get("domain"),
                port=item.get("port"),
            )
        )


def _import_settings(db: Session, items) -> None:
    for item in items:
        key = (item.get("key") or "").strip()
        if not key:
            raise ValueError("setting key is required")
        value = item.get("value") or ""
        existing = db.get(Setting, key)
        if existing is None:
            db.add(Setting(key=key, value=value))
        else:
            existing.value = value


def reset_all(db: Session) -> None:
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    db.query(User).delete()
    db.commit()
    seed_default_admin()