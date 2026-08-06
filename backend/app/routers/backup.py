from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.services.backup_service import export_backup

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