from sqlalchemy.orm import Session

from app.models import ExternalTarget
from app.schemas import ExternalTargetCreate, ExternalTargetUpdate


def external_target_to_dict(t: ExternalTarget) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "ip_address": t.ip_address,
        "domain": t.domain,
        "port": t.port,
        "ip_status": t.ip_status,
        "ip_latency_ms": t.ip_latency_ms,
        "ip_last_check": t.ip_last_check,
        "domain_status": t.domain_status,
        "domain_latency_ms": t.domain_latency_ms,
        "domain_last_check": t.domain_last_check,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def create_external_target(db: Session, data: ExternalTargetCreate) -> ExternalTarget:
    if not data.ip_address and not data.domain:
        raise ValueError("ip_address or domain is required")
    target = ExternalTarget(**data.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def update_external_target(
    db: Session, target_id: int, data: ExternalTargetUpdate
) -> ExternalTarget:
    target = db.get(ExternalTarget, target_id)
    if target is None:
        raise KeyError("target not found")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(target, key, value)
    if not target.ip_address and not target.domain:
        raise ValueError("ip_address or domain is required")
    db.commit()
    db.refresh(target)
    return target


def delete_external_target(db: Session, target_id: int) -> int:
    target = db.get(ExternalTarget, target_id)
    if target is None:
        raise KeyError("target not found")
    db.delete(target)
    db.commit()
    return target_id
