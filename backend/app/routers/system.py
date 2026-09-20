from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.deps import require_admin
from app.models import User
from app.services.update_service import check_github_update, apply_update_package

router = APIRouter()


class ApplyUpdateRequest(BaseModel):
    download_url: str
    mirror: Optional[str] = ""


@router.get("/update/check")
async def check_update(
    mirror: Optional[str] = Query(default=""),
    admin: User = Depends(require_admin),
):
    try:
        return await check_github_update(mirror=mirror)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/update/apply")
def apply_update(
    req: ApplyUpdateRequest,
    admin: User = Depends(require_admin),
):
    try:
        return apply_update_package(download_url=req.download_url, mirror=req.mirror)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
