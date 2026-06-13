from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from database import (
    get_store_by_id,
    get_store_by_license_key,
    list_stores,
    update_store_license,
)
from database import datetime_now
from realtime import hub
from datetime import timedelta, datetime, timezone


router = APIRouter(prefix="/api/v1/licenses", tags=["licenses"])


class LicenseUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    storeId: int | None = None
    expiresAt: str | None = None


class LicenseReactivateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    renewalMode: str | None = None
    expiresAt: str | None = None


def _parse_expiry(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


@router.get("")
def list_licenses() -> list[dict]:
    return list_stores()


@router.get("/resolve/{license_key}")
def resolve_license(license_key: str) -> dict:
    store = get_store_by_license_key(license_key)
    if store is None:
        raise HTTPException(status_code=404, detail="License not found")
    return store


@router.post("/{store_id}/activate")
def activate_license(store_id: int, payload: LicenseReactivateInput | None = None) -> dict:
    store = get_store_by_id(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    expires_at = store.get("license_expires_at", "")
    if payload:
        if payload.renewalMode == "lifetime":
            expires_at = ""
        elif payload.renewalMode == "year":
            expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        elif payload.renewalMode == "three_months":
            expires_at = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        elif payload.renewalMode == "custom" and payload.expiresAt:
            expires_at = payload.expiresAt
        elif payload.expiresAt:
            expires_at = payload.expiresAt
        else:
            current_expiry = _parse_expiry(expires_at)
            now = datetime.now(timezone.utc)
            if current_expiry is None or current_expiry <= now:
                expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    updated = update_store_license(
        store_id,
        status="ACTIVE",
        activated_at=datetime_now(),
        deactivated_at="",
        expires_at=expires_at,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to activate license")
    hub.publish("updated", "license", updated)
    return updated


@router.post("/{store_id}/deactivate")
def deactivate_license(store_id: int) -> dict:
    store = get_store_by_id(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    updated = update_store_license(
        store_id,
        status="INACTIVE",
        deactivated_at=datetime_now(),
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to deactivate license")
    hub.publish("updated", "license", updated)
    return updated


@router.put("/{store_id}/expires-at")
def set_license_expiration(store_id: int, payload: LicenseUpdateInput) -> dict:
    store = get_store_by_id(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    updated = update_store_license(
        store_id,
        expires_at=payload.expiresAt or "",
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to update license expiration")
    hub.publish("updated", "license", updated)
    return updated
