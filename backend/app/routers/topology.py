from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.services.lldp import apply_lldp_topology, discover_all_lldp_topology

router = APIRouter()


class ApplyLldpRequest(BaseModel):
    links: List[Dict[str, Any]]
    update_hierarchy: bool = True


@router.get("/lldp-neighbors")
def get_lldp_neighbors(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Scan all switches via LLDP-MIB and discover physical neighbor connections."""
    try:
        return discover_all_lldp_topology(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover LLDP topology: {str(e)}",
        )


@router.post("/apply-lldp")
def apply_lldp_connections(
    req: ApplyLldpRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """Solidify selected LLDP physical links into Device port_bindings and hierarchy."""
    try:
        return apply_lldp_topology(db, req.links, update_hierarchy=req.update_hierarchy)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply LLDP topology: {str(e)}",
        )


@router.get("/diag")
def diag_device_lldp(
    ip: str,
    community: str | None = None,
    port: int = 161,
    version: str = "v2c",
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Diagnose LLDP & SNMP connectivity for a single switch IP."""
    from sqlalchemy import select
    from app.models import Device
    from app.services.lldp import diag_lldp_connection

    # If community not provided, try resolving from Device record
    if not community:
        dev = db.scalars(select(Device).where(Device.ip_address == ip)).first()
        if dev:
            community = dev.snmp_community or "public"
            port = dev.snmp_port or 161
            version = dev.snmp_version or "v2c"
        else:
            community = "public"

    return diag_lldp_connection(ip=ip, community=community, port=port, version=version)

