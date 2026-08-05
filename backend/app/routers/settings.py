from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.setting_service import get_poll_interval, set_poll_interval

router = APIRouter()


class InspectionIntervalUpdate(BaseModel):
    poll_interval_minutes: int = Field(ge=1, le=1440)


@router.get("/inspection-interval")
def get_inspection_interval(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"poll_interval_minutes": get_poll_interval(db)}


@router.put("/inspection-interval")
def update_inspection_interval(
    payload: InspectionIntervalUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    minutes = set_poll_interval(db, payload.poll_interval_minutes)
    reschedule_interval(minutes)
    return {"poll_interval_minutes": minutes}
