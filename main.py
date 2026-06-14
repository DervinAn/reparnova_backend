import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from database import activate_store, get_device_by_fingerprint, get_device_by_key, init_db, touch_device
from routes.analytics import router as analytics_router
from routes.categories import router as categories_router
from routes.customers import router as customers_router
from routes.expenses import router as expenses_router
from routes.employees import router as employees_router
from routes.invoices import router as invoices_router
from routes.license import router as license_router
from routes.licenses import router as licenses_router
from routes.meta import router as meta_router
from routes.product_bundles import router as product_bundles_router
from routes.products import router as products_router
from routes.products import storage_router as storage_router
from routes.spare_parts import router as spare_parts_router
from routes.repairs import router as repairs_router
from routes.stores import router as stores_router
from routes.settings import router as settings_router
from routes.sync import router as sync_router
from realtime import hub


app = FastAPI(title="ReparNova Backend", version="1.0.0")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    hub.set_loop(asyncio.get_running_loop())


@app.middleware("http")
async def store_context_middleware(request: Request, call_next):
    from starlette.concurrency import run_in_threadpool

    path = request.url.path
    open_paths = {"/", "/health", "/api/v1/meta"}
    if path in open_paths or path.startswith("/api/v1/stores") or path.startswith("/openapi") or path.startswith("/docs") or path.startswith("/redoc"):
        response = await call_next(request)
        return response

    store_id_header = request.headers.get("X-Store-Id")
    store_code = request.headers.get("X-Store-Code")
    store_id = None
    if store_id_header:
        try:
            store_id = int(store_id_header)
        except ValueError:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=400, content={"detail": "Invalid X-Store-Id header"})
    
    store = await run_in_threadpool(activate_store, code=store_code, store_id=store_id)

    device_key = request.headers.get("X-Device-Key")
    device_fingerprint = request.headers.get("X-Device-Fingerprint", "")
    if device_key:
        device = await run_in_threadpool(get_device_by_key, device_key)
        if device is None or int(device["store_id"]) != int(store["id"]):
            if device_fingerprint:
                fallback_device = await run_in_threadpool(get_device_by_fingerprint, device_fingerprint)
                if fallback_device is not None and int(fallback_device["store_id"]) == int(store["id"]):
                    device = fallback_device
        if device is None or int(device["store_id"]) != int(store["id"]):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=401, content={"detail": "Invalid device key"})
        await run_in_threadpool(touch_device, device["device_key"])

    response = await call_next(request)
    return response


app.include_router(meta_router)
app.include_router(products_router)
app.include_router(product_bundles_router)
app.include_router(storage_router)
app.include_router(categories_router)
app.include_router(expenses_router)
app.include_router(spare_parts_router)
app.include_router(employees_router)
app.include_router(customers_router)
app.include_router(invoices_router)
app.include_router(repairs_router)
app.include_router(stores_router)
app.include_router(settings_router)
app.include_router(license_router)
app.include_router(licenses_router)
app.include_router(analytics_router)
app.include_router(sync_router)
