import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Device, User
from app.services import device_types as dt

router = APIRouter()

TYPE_NAME_PATTERN = r"^[a-zA-Z0-9_-]{1,20}$"
_type_re = re.compile(TYPE_NAME_PATTERN)


class DeviceTypeCreate(BaseModel):
    name: str


@router.get("/device-types")
def list_device_types(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    return {"builtin": dt.BUILTIN_TYPES, "custom": dt.get_custom_types(db)}


@router.post("/device-types", status_code=201)
def add_device_type(
    payload: DeviceTypeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = (payload.name or "").strip()
    if not _type_re.match(name):
        raise HTTPException(status_code=422, detail="类型名须为 1-20 位字母/数字/下划线/连字符")
    if name in dt.BUILTIN_TYPES:
        raise HTTPException(status_code=409, detail="内置类型不可重复添加")
    custom = dt.get_custom_types(db)
    if name in custom:
        raise HTTPException(status_code=409, detail="类型已存在")
    custom.append(name)
    dt.set_custom_types(db, custom)
    return {"ok": True, "custom": dt.get_custom_types(db)}


@router.delete("/device-types/{name}")
def remove_device_type(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if name in dt.BUILTIN_TYPES:
        raise HTTPException(status_code=400, detail="内置类型不可删除")
    custom = dt.get_custom_types(db)
    if name not in custom:
        raise HTTPException(status_code=404, detail="自定义类型不存在")
    custom = [x for x in custom if x != name]
    dt.set_custom_types(db, custom)
    db.execute(update(Device).where(Device.type == name).values(type="terminal"))
    db.commit()
    return {"ok": True}