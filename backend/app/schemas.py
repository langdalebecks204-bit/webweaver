from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: datetime


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="group", pattern="^(group|server|switch|terminal)$")
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    order_index: int = 0


class DeviceCreate(DeviceBase):
    parent_id: int | None = None


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, pattern="^(group|server|switch|terminal)$")
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    parent_id: int | None = None
    order_index: int | None = None


class DeviceOut(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    status: str
    latency_ms: int | None
    last_check: datetime | None
    children: list["DeviceOut"] = []


DeviceOut.model_rebuild()


class ExternalTargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip_address: str | None = None
    domain: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ExternalTargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip_address: str | None = None
    domain: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ExternalTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip_address: str | None
    domain: str | None
    port: int | None
    ip_status: str
    ip_latency_ms: int | None
    ip_last_check: datetime | None
    domain_status: str
    domain_latency_ms: int | None
    domain_last_check: datetime | None
    created_at: datetime
    updated_at: datetime
