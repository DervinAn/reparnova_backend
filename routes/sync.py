from __future__ import annotations

from fastapi import APIRouter, WebSocket

from database import activate_store, get_device_by_key, get_store_by_code
from realtime import websocket_store_sync


router = APIRouter(tags=["sync"])


@router.websocket("/api/v1/stores/{store_code}/ws")
async def store_sync_socket(websocket: WebSocket, store_code: str) -> None:
    store = get_store_by_code(store_code)
    if store is None:
        await websocket.close(code=1008)
        return

    device_key = websocket.query_params.get("deviceKey")
    if device_key:
        device = get_device_by_key(device_key)
        if device is None or int(device["store_id"]) != int(store["id"]):
            await websocket.close(code=1008)
            return

    activate_store(code=store_code)
    await websocket_store_sync(websocket, store_code)

