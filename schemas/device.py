from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DeviceCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    platform: str = "desktop"


class DeviceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    storeId: int
    name: str
    platform: str
    deviceKey: str
    active: bool
    lastSeen: str
    createdAt: str

