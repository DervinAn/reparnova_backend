from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from database import active_store, active_store_db_path, get_store_by_db_path


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, store_key: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[store_key].add(websocket)
        await websocket.send_json({"type": "connected", "storeKey": store_key})

    async def disconnect(self, store_key: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.get(store_key, set()).discard(websocket)
            if not self._clients.get(store_key):
                self._clients.pop(store_key, None)

    async def broadcast(self, store_key: str, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients.get(store_key, set()))
        for websocket in clients:
            try:
                await websocket.send_json(message)
            except Exception:
                await self.disconnect(store_key, websocket)

    def publish(self, event_type: str, entity: str, payload: dict[str, Any] | None = None) -> None:
        store = active_store()
        if store is None:
            store = get_store_by_db_path(active_store_db_path())
        if store is None:
            return
        store_key = str(store["code"])
        message = {
            "type": event_type,
            "entity": entity,
            "storeId": store["id"],
            "storeCode": store["code"],
            "payload": payload or {},
        }
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(store_key, message), self._loop)


hub = RealtimeHub()


async def websocket_store_sync(websocket: WebSocket, store_key: str) -> None:
    await hub.connect(store_key, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(store_key, websocket)
    except Exception:
        await hub.disconnect(store_key, websocket)
