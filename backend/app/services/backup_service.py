from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device, ExternalTarget, Setting, utcnow

BACKUP_VERSION = 1


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