from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.backup_service import export_backup, import_backup, reset_all
from app.services.setting_service import get_poll_interval

router = APIRouter()


@router.get("/export")
def export_backup_endpoint(
    include_devices: bool | None = None,
    include_external: bool | None = None,
    include_settings: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if include_devices is None and include_external is None and include_settings is None:
        include_devices = include_external = include_settings = True
    else:
        include_devices = bool(include_devices)
        include_external = bool(include_external)
        include_settings = bool(include_settings)
    return export_backup(db, include_devices, include_external, include_settings)


@router.post("/import")
async def import_backup_endpoint(
    request: Request,
    mode: str = Query("replace", pattern="^(replace|merge)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="invalid JSON body")
    try:
        import_backup(db, data, mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    reschedule_interval(get_poll_interval(db))
    return {"ok": True, "mode": mode}


@router.post("/reset")
def reset_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    reset_all(db)
    reschedule_interval(settings.poll_interval_minutes)
    return {"ok": True}