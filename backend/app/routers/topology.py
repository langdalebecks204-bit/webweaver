from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.services.lldp import apply_lldp_topology, discover_all_lldp_topology
from app.services.fdb_edge import apply_edge_topology, discover_edge_topology

router = APIRouter()


class ApplyLldpRequest(BaseModel):
    links: List[Dict[str, Any]]
    update_hierarchy: bool = True


class EdgeDiscoverRequest(BaseModel):
    switch_ids: List[int] | None = None


class ApplyEdgeRequest(BaseModel):
    direct_terminals: List[Dict[str, Any]] = []
    hubs_to_create: List[Dict[str, Any]] = []


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


@router.post("/edge-discover")
def discover_edge(
    req: EdgeDiscoverRequest | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Scan switch FDB tables and discover direct terminals, unmanaged hubs, and AP clusters."""
    try:
        switch_ids = req.switch_ids if req else None
        return discover_edge_topology(db, switch_ids=switch_ids)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover edge topology: {str(e)}",
        )


@router.post("/apply-edge")
def apply_edge(
    req: ApplyEdgeRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """Apply edge selections into database (bind direct terminals and create virtual hubs)."""
    try:
        res = apply_edge_topology(
            db,
            direct_terminals=req.direct_terminals,
            hubs_to_create=req.hubs_to_create,
        )
        return {"status": "ok", **res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply edge topology: {str(e)}",
        )


