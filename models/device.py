from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Device:
    id: int
    storeId: int
    name: str
    platform: str
    deviceKey: str
    active: bool
    lastSeen: str
    createdAt: str

