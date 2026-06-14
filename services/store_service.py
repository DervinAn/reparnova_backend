from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from database import (
    activate_device_by_key,
    activate_store,
    create_device,
    create_store,
    delete_store,
    get_connection,
    get_store_by_id,
    get_store_by_license_key,
    list_devices,
    list_stores,
    request_device_activation,
    update_store,
)


class StoreCreateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    phone: str = ""
    address: str = ""
    code: str | None = None
    deviceLimit: int = 2
    firstDeviceName: str = "Main Device"
    platform: str = "desktop"


class StoreUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    deviceLimit: int | None = None


class DeviceCreateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    platform: str = "desktop"


class DeviceRequestInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    licenseKey: str
    deviceFingerprint: str
    deviceName: str = "Desktop"
    platform: str = "desktop"


class StoreSummaryOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    storeId: int
    storeCode: str
    storeName: str
    productsCount: int = 0
    sparePartsCount: int = 0
    productBundlesCount: int = 0
    employeesCount: int = 0
    invoicesCount: int = 0
    repairsCount: int = 0
    customersCount: int = 0
    completedSalesTotal: float = 0.0
    deviceCount: int = 0
    pendingDeviceCount: int = 0
    deviceLimit: int = 0


def create_store_with_device(input: StoreCreateInput) -> dict:
    store = create_store(input.name, input.phone, input.address, input.code, input.deviceLimit)
    device = create_device(int(store["id"]), input.firstDeviceName, input.platform)
    return {"store": store, "device": device}


def get_store(store_id: int) -> dict | None:
    return get_store_by_id(store_id)


def get_all_stores() -> list[dict]:
    return list_stores()


def get_store_devices(store_id: int) -> list[dict]:
    return list_devices(store_id)


def add_store_device(store_id: int, input: DeviceCreateInput) -> dict:
    return create_device(store_id, input.name, input.platform)


def remove_store(store_id: int) -> dict | None:
    return delete_store(store_id)


def update_store_details(store_id: int, input: StoreUpdateInput) -> dict | None:
    return update_store(
        store_id,
        name=input.name,
        phone=input.phone,
        address=input.address,
        device_limit=input.deviceLimit,
    )


def get_store_summary(store_id: int) -> dict:
    store = get_store_by_id(store_id)
    if store is None:
        raise ValueError("Store not found")

    activate_store(store_id=store_id)
    with get_connection() as conn:
        products = conn.execute("SELECT COUNT(*) AS count FROM products").fetchone() or {"count": 0}
        spare_parts = conn.execute("SELECT COUNT(*) AS count FROM spare_parts").fetchone() or {"count": 0}
        bundles = conn.execute("SELECT COUNT(*) AS count FROM product_bundles").fetchone() or {"count": 0}
        employees = conn.execute("SELECT COUNT(*) AS count FROM users WHERE active = 1").fetchone() or {"count": 0}
        invoices = conn.execute("SELECT COUNT(*) AS count FROM invoices").fetchone() or {"count": 0}
        repairs = conn.execute("SELECT COUNT(*) AS count FROM repairs").fetchone() or {"count": 0}
        customers = conn.execute("SELECT COUNT(*) AS count FROM customers WHERE is_active = 1").fetchone() or {"count": 0}
        completed_sales = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS total FROM invoices WHERE status = 'COMPLETED'"
        ).fetchone() or {"total": 0}
        device_rows = list_devices(store_id)
        active_devices = sum(1 for device in device_rows if int(device.get("active") or 0) == 1)
        pending_devices = sum(1 for device in device_rows if int(device.get("active") or 0) == 0)

    return {
        "storeId": int(store["id"]),
        "storeCode": store["code"],
        "storeName": store["name"],
        "productsCount": int(products["count"]),
        "sparePartsCount": int(spare_parts["count"]),
        "productBundlesCount": int(bundles["count"]),
        "employeesCount": int(employees["count"]),
        "invoicesCount": int(invoices["count"]),
        "repairsCount": int(repairs["count"]),
        "customersCount": int(customers["count"]),
        "completedSalesTotal": float(completed_sales["total"]),
        "deviceCount": active_devices,
        "pendingDeviceCount": pending_devices,
        "deviceLimit": int(store.get("device_limit") or 0),
    }


def request_store_device_activation(input: DeviceRequestInput) -> dict:
    store = get_store_by_license_key(input.licenseKey)
    if store is None:
        raise ValueError("License not found")
    device = request_device_activation(
        int(store["id"]),
        name=input.deviceName,
        platform=input.platform,
        device_fingerprint=input.deviceFingerprint,
    )
    return {"store": store, "device": device}


def activate_store_device(device_key: str) -> dict | None:
    return activate_device_by_key(device_key)
