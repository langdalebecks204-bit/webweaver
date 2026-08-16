from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.inspector.scheduler import reschedule_interval
from app.models import User
from app.services.setting_service import (
    get_ping_params,
    get_poll_interval,
    get_probe_history_days,
    set_ping_params,
    set_poll_interval,
    set_probe_history_days,
)

router = APIRouter()


class InspectionIntervalUpdate(BaseModel):
    poll_interval_minutes: int = Field(ge=1, le=1440)


class ProbeHistoryDaysUpdate(BaseModel):
    probe_history_days: int = Field(ge=1, le=365)


class PingParamsUpdate(BaseModel):
    ping_count: int = Field(ge=1, le=10)
    ping_packet_size: int = Field(ge=32, le=10000)


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


@router.get("/probe-history-days")
def get_probe_history_days_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"probe_history_days": get_probe_history_days(db)}


@router.put("/probe-history-days")
def update_probe_history_days_route(
    payload: ProbeHistoryDaysUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    days = set_probe_history_days(db, payload.probe_history_days)
    return {"probe_history_days": days}


@router.get("/ping-params")
def get_ping_params_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    count, size = get_ping_params(db)
    return {"ping_count": count, "ping_packet_size": size}


@router.put("/ping-params")
def update_ping_params_route(
    payload: PingParamsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    count, size = set_ping_params(db, payload.ping_count, payload.ping_packet_size)
    return {"ping_count": count, "ping_packet_size": size}
