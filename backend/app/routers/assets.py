from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.schemas import DeviceCreate
from app.services.arp import get_consolidated_assets
from app.services.device_service import create_device, device_to_dict

router = APIRouter()


@router.get("", response_model=List[Dict[str, Any]])
def list_assets(
    target_device_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Retrieve full-network or single-switch IP-MAC asset table merged with known devices."""
    try:
        return get_consolidated_assets(db, target_device_id=target_device_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch assets: {str(e)}",
        )


@router.post("/scan", response_model=List[Dict[str, Any]])
def scan_assets(
    target_device_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """Trigger immediate ARP scan on switches and host to refresh IP-MAC assets."""
    try:
        return get_consolidated_assets(db, target_device_id=target_device_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan assets: {str(e)}",
        )


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
def enroll_asset(
    data: DeviceCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """One-click enroll an unmanaged asset into the Device tree."""
    try:
        dev = create_device(db, data)
        return device_to_dict(dev)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll device: {str(e)}",
        )
