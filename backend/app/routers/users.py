from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import UserOut
from app.security import hash_password

router = APIRouter()


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="viewer", pattern="^(admin|viewer)$")


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|viewer)$")


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.scalars(select(User).where(User.username == payload.username)).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="cannot delete yourself")
    db.delete(user)
    db.commit()
    return {"deleted": user.id}
