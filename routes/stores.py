from fastapi import APIRouter, HTTPException

from services.store_service import (
    DeviceCreateInput,
    StoreCreateInput,
    StoreUpdateInput,
    activate_store_device,
    add_store_device,
    create_store_with_device,
    get_store_summary,
    get_all_stores,
    get_store,
    get_store_devices,
    remove_store,
    update_store_details,
)
from database import get_store_by_code, set_active_store
from realtime import hub


router = APIRouter(prefix="/api/v1/stores", tags=["stores"])


@router.get("")
def list_stores() -> list[dict]:
    return get_all_stores()


@router.post("")
def create_store(payload: StoreCreateInput) -> dict:
    return create_store_with_device(payload)


@router.put("/{store_id}")
def update_store(store_id: int, payload: StoreUpdateInput) -> dict:
    store = update_store_details(store_id, payload)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.delete("/{store_id}")
def delete_store(store_id: int) -> dict:
    store = get_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    set_active_store(store)
    hub.publish("updated", "license", store)
    removed = remove_store(store_id)
    if removed is None:
        raise HTTPException(status_code=500, detail="Unable to delete store")
    return {"deleted": True, "store": store}


@router.get("/{store_id}")
def read_store(store_id: int) -> dict:
    store = get_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}/summary")
def read_store_summary(store_id: int) -> dict:
    try:
        return get_store_summary(store_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/resolve/{code}")
def resolve_store(code: str) -> dict:
    store = get_store_by_code(code)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}/devices")
def read_store_devices(store_id: int) -> list[dict]:
    return get_store_devices(store_id)


@router.post("/{store_id}/devices")
def create_store_device(store_id: int, payload: DeviceCreateInput) -> dict:
    store = get_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        return add_store_device(store_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{store_id}/devices/{device_key}/activate")
def activate_store_device_route(store_id: int, device_key: str) -> dict:
    store = get_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        device = activate_store_device(device_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if device is None or int(device.get("store_id") or 0) != int(store_id):
        raise HTTPException(status_code=404, detail="Device not found")
    hub.publish("updated", "stores", store)
    return device
