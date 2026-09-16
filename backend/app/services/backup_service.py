from datetime import datetime
import io
import json
import os
from typing import Any
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import seed_default_admin
from app.models import Device, ExternalTarget, ProbeRecord, Setting, User, utcnow
from app.services.image_service import clear_all_images

BACKUP_VERSION = 2


def _format_datetime(val: Any) -> str:
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, str):
        return val
    return ""


def _parse_datetime(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str) and val:
        try:
            return datetime.fromisoformat(val)
        except Exception:
            try:
                return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None
    return None


def _to_timestamp(val: Any) -> int | None:
    dt = _parse_datetime(val)
    if dt is not None:
        try:
            return int(dt.timestamp())
        except Exception:
            return None
    return None


def _stream_history_to_zip(db: Session, zf: zipfile.ZipFile) -> None:
    stmt = (
        select(
            ProbeRecord.device_id,
            ProbeRecord.checked_at,
            ProbeRecord.status,
            ProbeRecord.latency_ms,
        )
        .order_by(ProbeRecord.device_id, ProbeRecord.checked_at)
        .execution_options(yield_per=1000)
    )
    with zf.open("history.jsonl", "w") as f:
        for row in db.execute(stmt):
            dt_str = _format_datetime(row[1])
            if not dt_str:
                continue
            line = (
                json.dumps(
                    {
                        "device_id": row[0],
                        "checked_at": dt_str,
                        "status": row[2],
                        "latency_ms": row[3],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.write(line.encode("utf-8"))


def _valid_types(db: Session) -> set[str]:
    from app.services.device_types import BUILTIN_TYPES, get_custom_types

    return set(BUILTIN_TYPES) | set(get_custom_types(db))


def export_backup(
    db: Session,
    include_devices: bool = True,
    include_external: bool = True,
    include_settings: bool = True,
    include_images: bool = True,
    include_history: bool = True,
) -> bytes:
    data: dict = {"version": BACKUP_VERSION, "exported_at": utcnow().isoformat()}
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

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("weaver.json", json.dumps(data, ensure_ascii=False, indent=2))
        if include_devices and include_history:
            _stream_history_to_zip(db, zf)
        if include_devices and include_images:
            _write_images_to_zip(zf)
    return buf.getvalue()


def _write_images_to_zip(zf: zipfile.ZipFile) -> None:
    for full in _iter_uploaded_images():
        zf.write(full, arcname=f"images/{os.path.basename(full)}")


def _iter_uploaded_images():
    if not os.path.isdir(settings.upload_dir):
        return
    for entry in sorted(os.listdir(settings.upload_dir)):
        full = os.path.join(settings.upload_dir, entry)
        if os.path.isfile(full) and entry.endswith(".jpg"):
            yield full


def _flatten_devices(devices: list[Device]) -> list[dict]:
    by_parent: dict[int | None, list[Device]] = {}
    node_ids = {d.id for d in devices}
    for d in devices:
        by_parent.setdefault(d.parent_id, []).append(d)
    out: list[dict] = []

    def walk(d: Device) -> None:
        item = {
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "ip_address": d.ip_address,
            "port": d.port,
            "location": d.location,
            "port_count": d.port_count,
            "uplink_port": d.uplink_port,
            "port_bindings": d.port_bindings,
            "snmp_community": d.snmp_community,
            "snmp_version": d.snmp_version,
            "snmp_port": d.snmp_port,
            "order_index": d.order_index,
            "parent_id": d.parent_id,
        }
        if d.image_url:
            item["image_file"] = f"images/{d.id}.jpg"
        out.append(item)
        for child in sorted(by_parent.get(d.id, []), key=lambda x: (x.order_index, x.id)):
            walk(child)

    for d in sorted(devices, key=lambda x: (x.order_index, x.id)):
        if d.parent_id is None or d.parent_id not in node_ids:
            walk(d)
    return out


def import_backup(db: Session, raw: bytes | dict, mode: str) -> None:
    if isinstance(raw, dict):
        data, images = raw, {}
        history_iter = raw.get("records")
    elif raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            if "weaver.json" not in zf.namelist():
                raise ValueError("zip is missing weaver.json")
            data = json.loads(zf.read("weaver.json"))
            images = {
                name: zf.read(name)
                for name in zf.namelist()
                if name.startswith("images/") and not name.endswith("/")
            }
            if "history.jsonl" in zf.namelist():
                def _stream_lines():
                    with zf.open("history.jsonl") as hf:
                        for line in hf:
                            line = line.strip()
                            if line:
                                try:
                                    yield json.loads(line.decode("utf-8"))
                                except Exception:
                                    pass
                history_iter = _stream_lines()
            else:
                history_iter = data.get("records")
            _execute_import(db, data, images, history_iter, mode)
            db.commit()
            return
    else:
        try:
            data = json.loads(raw)
        except Exception:
            raise ValueError("invalid backup file")
        images = {}
        history_iter = data.get("records")

    _execute_import(db, data, images, history_iter, mode)
    db.commit()


def _execute_import(
    db: Session,
    data: dict,
    images: dict[str, bytes],
    history_iter: Any,
    mode: str,
) -> None:
    if not isinstance(data, dict) or data.get("version") not in (1, 2):
        raise ValueError("unsupported backup version")
    if mode == "replace":
        _import_replace(db, data, images, history_iter)
    else:
        _import_merge(db, data, images, history_iter)


def _parse_import_bytes(raw: bytes) -> tuple[dict, dict[str, bytes]]:
    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            if "weaver.json" not in zf.namelist():
                raise ValueError("zip is missing weaver.json")
            data = json.loads(zf.read("weaver.json"))
            images = {
                name: zf.read(name)
                for name in zf.namelist()
                if name.startswith("images/") and not name.endswith("/")
            }
            if "history.jsonl" in zf.namelist():
                records = []
                with zf.open("history.jsonl") as hf:
                    for line in hf:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line.decode("utf-8")))
                            except Exception:
                                pass
                data["records"] = records
        return data, images
    try:
        return json.loads(raw), {}
    except Exception:
        raise ValueError("invalid backup file")


def _import_replace(
    db: Session,
    data: dict,
    images: dict[str, bytes],
    history_iter: Any,
) -> None:
    db.query(ProbeRecord).delete()
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    clear_all_images()
    _import_settings(db, data.get("settings", []))
    id_map = _import_devices(db, data.get("devices", []), merge=False, images=images)
    _import_history(db, history_iter, id_map, merge=False)
    _import_external(db, data.get("external", []), merge=False)


def _import_merge(
    db: Session,
    data: dict,
    images: dict[str, bytes],
    history_iter: Any,
) -> None:
    id_map = _import_devices(db, data.get("devices", []), merge=True, images=images)
    _import_history(db, history_iter, id_map, merge=True)
    _import_external(db, data.get("external", []), merge=True)
    _import_settings(db, data.get("settings", []))


def _import_devices(
    db: Session, items: list[dict], merge: bool, images: dict[str, bytes]
) -> None:
    id_map: dict[int, int] = {}
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("device name is required")
        dev_type = item.get("type") or "group"
        if dev_type not in _valid_types(db):
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
            location=item.get("location"),
            port_count=item.get("port_count"),
            uplink_port=item.get("uplink_port"),
            port_bindings=item.get("port_bindings"),
            snmp_community=item.get("snmp_community") or "public",
            snmp_version=item.get("snmp_version") or "v2c",
            snmp_port=item.get("snmp_port") or 161,
            order_index=item.get("order_index") or 0,
            parent_id=parent_id,
        )
        db.add(device)
        db.flush()
        id_map[item["id"]] = device.id
        _restore_image(device, item.get("image_file"), images)
    return id_map


def _restore_image(device: Device, image_file: str | None, images: dict[str, bytes]) -> None:
    if not image_file:
        return
    content = images.get(image_file)
    if content is None:
        return
    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = f"{device.id}.jpg"
    Path(settings.upload_dir, filename).write_bytes(content)
    device.image_url = f"/uploads/{filename}"


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
    db.flush()


def reset_all(db: Session) -> None:
    db.query(ProbeRecord).delete()
    db.query(Device).delete()
    db.query(ExternalTarget).delete()
    db.query(Setting).delete()
    db.query(User).delete()
    db.commit()
    clear_all_images()
    seed_default_admin()


def _import_history(
    db: Session, items: Any, id_map: dict[int, int], merge: bool
) -> None:
    if not items:
        return
    existing_keys = set()
    if merge:
        rows = db.execute(select(ProbeRecord.device_id, ProbeRecord.checked_at)).all()
        for r in rows:
            ts = _to_timestamp(r[1])
            if ts is not None:
                existing_keys.add((r[0], ts))

    batch = []
    for item in items:
        old_dev_id = item.get("device_id")
        new_dev_id = id_map.get(old_dev_id)
        if new_dev_id is None:
            continue
        raw_checked_at = item.get("checked_at")
        checked_at = _parse_datetime(raw_checked_at)
        if checked_at is None:
            continue
        if merge:
            ts = _to_timestamp(checked_at)
            if ts is not None and (new_dev_id, ts) in existing_keys:
                continue
        batch.append(
            {
                "device_id": new_dev_id,
                "checked_at": checked_at,
                "status": item.get("status") or "unknown",
                "latency_ms": item.get("latency_ms"),
            }
        )
        if len(batch) >= 500:
            db.bulk_insert_mappings(ProbeRecord, batch)
            db.flush()
            batch.clear()
    if batch:
        db.bulk_insert_mappings(ProbeRecord, batch)
        db.flush()
