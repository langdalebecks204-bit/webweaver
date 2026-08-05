from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.inspector.engine import run_external_inspection
from app.models import ExternalTarget, User
from app.schemas import ExternalTargetCreate, ExternalTargetOut, ExternalTargetUpdate
from app.services.external_service import (
    create_external_target,
    delete_external_target,
    external_target_to_dict,
    update_external_target,
)

router = APIRouter()


@router.get("")
def list_external_targets(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return [
        external_target_to_dict(t)
        for t in db.scalars(select(ExternalTarget).order_by(ExternalTarget.id))
    ]


@router.post("/check-all")
async def check_all_external_targets(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    targets = list(db.scalars(select(ExternalTarget).order_by(ExternalTarget.id)))
    results = await run_external_inspection(db, targets)
    return {"checked": results}


@router.post("", response_model=ExternalTargetOut, status_code=201)
def create_target(
    payload: ExternalTargetCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        target = create_external_target(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return target


@router.put("/{target_id}", response_model=ExternalTargetOut)
def update_target(
    target_id: int,
    payload: ExternalTargetUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        target = update_external_target(db, target_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="External target not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return target


@router.delete("/{target_id}")
def delete_target(
    target_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        deleted = delete_external_target(db, target_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="External target not found")
    return {"deleted": deleted}
