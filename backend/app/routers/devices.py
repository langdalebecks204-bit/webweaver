from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.inspector.engine import run_external_inspection, run_inspection
from app.inspector.scheduler import collect_all_targets, collect_external_targets
from app.models import Device, ProbeRecord
from app.schemas import DeviceCreate, DeviceUpdate
from app.services.device_service import (
    build_tree,
    create_device as create_device_service,
    delete_device as delete_device_service,
    device_to_dict,
    get_descendant_ids,
    update_device as update_device_service,
)
from app.services.image_service import delete_image_file, upload_image

router = APIRouter()


def _get_or_404(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("")
def list_devices(
    status: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    query = select(Device).order_by(Device.order_index, Device.id)
    if status:
        query = query.where(Device.status == status)
    if type:
        query = query.where(Device.type == type)
    return [device_to_dict(d) for d in db.scalars(query)]


@router.get("/tree")
def get_tree(db: Session = Depends(get_db), _: object = Depends(get_current_user)):
    return build_tree(db)


@router.post("/recheck-all")
async def recheck_all_devices(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    targets = collect_all_targets(db)
    results = await run_inspection(db, targets)
    external = collect_external_targets(db)
    external_results = await run_external_inspection(db, external)
    return {"checked": results, "external_checked": external_results}


@router.get("/{device_id}")
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return device_to_dict(_get_or_404(db, device_id))


@router.get("/{device_id}/history")
def get_device_history(
    device_id: int,
    days: int = Query(default=7, ge=1),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    _get_or_404(db, device_id)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    records = db.scalars(
        select(ProbeRecord)
        .where(ProbeRecord.device_id == device_id, ProbeRecord.checked_at >= cutoff)
        .order_by(ProbeRecord.checked_at.desc())
    ).all()
    return {
        "device_id": device_id,
        "records": [
            {
                "checked_at": r.checked_at.replace(tzinfo=timezone.utc).isoformat(),
                "status": r.status,
                "latency_ms": r.latency_ms,
            }
            for r in records
        ],
    }


@router.post("", status_code=201)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    try:
        device = create_device_service(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return device_to_dict(device)


@router.put("/{device_id}")
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    try:
        device = update_device_service(db, device_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return device_to_dict(device)


@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    _get_or_404(db, device_id)
    deleted = delete_device_service(db, device_id)
    return {"deleted": deleted}


@router.post("/{device_id}/image", status_code=200)
def upload_device_image(
    device_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    device = _get_or_404(db, device_id)
    new_url = upload_image(device_id, file)
    device.image_url = new_url
    db.commit()
    db.refresh(device)
    return device_to_dict(device)


@router.delete("/{device_id}/image")
def delete_device_image(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    device = _get_or_404(db, device_id)
    delete_image_file(device_id)
    device.image_url = None
    db.commit()
    db.refresh(device)
    return device_to_dict(device)


@router.post("/{device_id}/recheck")
async def recheck_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    _get_or_404(db, device_id)
    ids = get_descendant_ids(db, device_id)
    targets = list(
        db.scalars(
            select(Device).where(
                Device.id.in_(ids),
                Device.ip_address.is_not(None),
            )
        )
    )
    results = await run_inspection(db, targets)
    return {"checked": results}


@router.get("/{device_id}/snmp/interfaces")
def get_device_snmp_interfaces(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    device = _get_or_404(db, device_id)
    if device.type != "switch":
        raise HTTPException(status_code=400, detail="Device is not a switch")
    if not device.ip_address:
        raise HTTPException(status_code=400, detail="Switch IP address not configured")

    from app.services.snmp import get_switch_interfaces
    interfaces = get_switch_interfaces(
        device_id=device.id,
        ip=device.ip_address,
        community=device.snmp_community or "public",
        port=device.snmp_port or 161,
        version=device.snmp_version or "v2c",
    )
    return {
        "device_id": device.id,
        "interfaces": interfaces,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

