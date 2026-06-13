"""ReparNova backend business logic and DTOs."""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from fastapi import Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, ConfigDict

from database import active_store_db_path, get_connection, init_db, json_dumps, json_loads, row_to_dict
from realtime import hub

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False

def to_money(value: Any) -> float:
    return float(value or 0)

def to_int(value: Any) -> int:
    return int(value or 0)


def publish_store_event(entity: str, action: str, payload: dict[str, Any] | None = None) -> None:
    hub.publish(f"{entity}.{action}", entity, payload)

class StockStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"

class PaymentMethod(str, Enum):
    CASH = "CASH"
    CARD = "CARD"
    BARIDIMOB = "BARIDIMOB"
    CREDIT = "CREDIT"

class SaleLineType(str, Enum):
    PRODUCT = "PRODUCT"
    BUNDLE = "BUNDLE"

class InvoiceStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class RepairStatus(str, Enum):
    RECEIVED = "RECEIVED"
    DIAGNOSING = "DIAGNOSING"
    WAITING_PARTS = "WAITING_PARTS"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    REPAIRED = "REPAIRED"
    DELIVERED = "DELIVERED"

class ExpenseStatus(str, Enum):
    PAID = "PAID"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"

class ExpensePaymentMethod(str, Enum):
    CASH = "CASH"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHECK = "CHECK"
    BARIDIMOB = "BARIDIMOB"
    CREDIT = "CREDIT"

class ExpenseOperationType(str, Enum):
    EXPENSE = "EXPENSE"
    WITHDRAW = "WITHDRAW"
    DEPOSIT = "DEPOSIT"

class RepairSyncState(str, Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    ERROR = "ERROR"

class CategoryType(str, Enum):
    PRODUCT = "PRODUCT"
    EXPENSE = "EXPENSE"
    SERVICE = "SERVICE"
    OTHER = "OTHER"

class ProductSpecification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    value: str = ""

class StorageLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    warehouse: str = ""
    zone: str = ""
    aisle: str = ""
    shelf: str = ""
    level: str = ""
    bin: str = ""

class ProductVariant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    optionName: str = ""
    values: str = ""

class ProductBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reference: str = ""
    name: str
    category: str = ""
    purchasePrice: float = 0
    salePrice: float = 0
    semiWholesalePrice: float = 0
    wholesalePrice: float = 0
    stock: int = 0
    sku: str
    imagePath: str = ""
    barcode: str = ""
    lowStockAlert: int = 5
    packaging: str = ""
    expirationDate: str = ""
    specifications: list[ProductSpecification] = Field(default_factory=list)
    storageLocation: StorageLocation = Field(default_factory=StorageLocation)
    variants: list[ProductVariant] = Field(default_factory=list)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    id: int

class ProductOut(ProductBase):
    id: int
    stockStatus: StockStatus
    createdAt: str
    updatedAt: str

class ProductBundleItemBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    productId: int = 0
    productSku: str = ""
    productSyncKey: str = ""
    quantity: int = 1

class ProductBundleItemOut(ProductBundleItemBase):
    productName: str = ""
    purchasePrice: float = 0
    salePrice: float = 0
    availableStock: int = 0

class ProductBundleBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    code: str = ""
    syncKey: str = ""
    bundlePrice: float = 0
    active: bool = True
    items: list[ProductBundleItemBase] = Field(default_factory=list)

class ProductBundleCreate(ProductBundleBase):
    pass

class ProductBundleUpdate(ProductBundleBase):
    id: int

class ProductBundleOut(ProductBundleBase):
    id: int
    createdAt: str = ""
    items: list[ProductBundleItemOut] = Field(default_factory=list)

class SparePartBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    syncKey: str = ""
    name: str
    typeModel: str = ""
    placement: str = ""
    qty: int = 0
    purchasePrice: float = 0

class SparePartCreate(SparePartBase):
    pass

class SparePartUpdate(SparePartBase):
    id: int

class SparePartOut(SparePartBase):
    id: int
    createdAt: str = ""

class ProductDuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    sku: str | None = None
    reference: str | None = None

class StoragePlacementInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    location: StorageLocation = Field(default_factory=StorageLocation)

class CategoryBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    iconKey: str = ""
    colorHex: str = "#111827"
    imagePath: str = ""
    type: CategoryType = CategoryType.PRODUCT
    parentId: int | None = None
    active: bool = True
    systemKey: str = ""

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    id: int

class CategoryOut(CategoryBase):
    id: int

class ExpenseBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date: str
    title: str
    category: str
    amount: float = 0
    operationType: ExpenseOperationType = ExpenseOperationType.EXPENSE
    paymentMethod: ExpensePaymentMethod = ExpensePaymentMethod.CASH
    status: ExpenseStatus = ExpenseStatus.PAID
    employeeName: str = ""
    note: str = ""

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(ExpenseBase):
    id: int

class ExpenseOut(ExpenseBase):
    id: int

class CustomerBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    phone: str = ""
    email: str = ""
    city: str = ""
    memberSince: str | None = None
    totalPurchases: float = 0
    debt: float = 0
    isActive: bool = True
    lastPayment: str = ""
    lastInvoice: str = ""

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(CustomerBase):
    id: int

class CustomerOut(CustomerBase):
    id: int

class EmployeeBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    employeeCode: str = ""
    fullName: str
    role: str = "STAFF"
    username: str = ""
    passwordHash: str = ""
    passwordSalt: str = ""
    department: str = "General"
    phone: str = ""
    salary: float = 0
    active: bool = True
    onLeave: bool = False
    createdAt: str = ""

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(EmployeeBase):
    id: int

class EmployeeOut(EmployeeBase):
    id: int
    hasPassword: bool = False

class InvoiceItemInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    sku: str = ""
    qty: int = 1
    unitPrice: float = 0
    unitCostSnapshot: float = 0
    lineType: SaleLineType = SaleLineType.PRODUCT
    bundleId: int | None = None

class InvoiceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoiceNumber: str | None = None
    syncKey: str = ""
    customerName: str = ""
    customerPhone: str = ""
    items: list[InvoiceItemInput] = Field(default_factory=list)
    paymentMethod: PaymentMethod = PaymentMethod.CASH
    status: InvoiceStatus = InvoiceStatus.COMPLETED
    sellerName: str = ""

class InvoiceEditInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    customerName: str
    customerPhone: str
    paymentMethod: PaymentMethod
    status: InvoiceStatus = InvoiceStatus.COMPLETED

class InvoiceItemOut(InvoiceItemInput):
    id: int
    invoiceId: int

class InvoiceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    syncKey: str = ""
    invoiceNumber: str
    customerName: str
    customerPhone: str
    items: list[InvoiceItemOut] = Field(default_factory=list)
    total: float
    paymentMethod: PaymentMethod
    status: InvoiceStatus
    dateTime: str
    sellerName: str = ""

class ReturnItemInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoiceItemName: str
    qtySold: int
    qtyReturn: int
    amount: float

class RefundRecordOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    invoiceNumber: str
    customerName: str
    items: list[ReturnItemInput]
    totalRefund: float
    paymentMethod: PaymentMethod
    createdAt: str

class RepairPart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    price: float = 0

class RepairBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    customerName: str
    phone: str = ""
    device: str
    color: str = ""
    imeiOrSerial: str = ""
    issue: str = ""
    parts: list[RepairPart] = Field(default_factory=list)
    technician: str = ""
    price: float = 0
    paymentMethod: PaymentMethod = PaymentMethod.CASH
    paid: bool = False
    status: RepairStatus = RepairStatus.RECEIVED
    date: str = Field(default_factory=utc_now)
    includedItems: str = ""
    trackingCode: str = ""
    syncState: RepairSyncState = RepairSyncState.PENDING

class RepairCreate(RepairBase):
    pass

class RepairUpdate(RepairBase):
    id: int

class RepairOut(RepairBase):
    id: int
    partsTotal: float
    totalPrice: float

class RepairStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: RepairStatus
    note: str = ""
    employeeName: str = ""

class StoreSettingsInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    storeName: str = ""
    phone1: str = ""
    phone2: str = ""
    address: str = ""
    social1: str = ""
    social2: str = ""
    logoPath: str = ""
    defaultPrinter: str = ""
    labelWidthMm: int = 40
    labelHeightMm: int = 20
    labelStoreNameX: float = 0.10
    labelStoreNameY: float = 0.14
    labelProductNameX: float = 0.10
    labelProductNameY: float = 0.30
    labelSkuX: float = 0.10
    labelSkuY: float = 0.44
    labelPriceX: float = 0.10
    labelPriceY: float = 0.88
    labelStoreNameColor: str = "#111827"
    labelProductNameColor: str = "#111827"
    labelSkuColor: str = "#64748B"
    labelPriceColor: str = "#111827"
    labelBarcodeX: float = 0.08
    labelBarcodeY: float = 0.54
    themeMode: str = "DARK"
    cashSoundMode: str = "DEFAULT"
    customCashSoundPath: str = ""
    chargilyApiKey: str = ""
    receiptLanguage: str = "AR"
    repairIncludedItems: str = ""

class StoreSettingsOut(StoreSettingsInput):
    pass

class AnalyticsSnapshotOut(BaseModel):
    sales: float
    lowStockItems: int
    customersCount: int
    netProfit: float
    customerDebtCollections: float = 0
    purchases: float = 0
    expenses: float = 0
    employeesCount: int = 0
    lowSellingItems: int = 0
    neverSoldItems: int = 0

class LicenseInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    activationCode: str = ""
    deviceHash: str = ""
    activatedAt: str = ""
    lastValidatedAt: str = ""
    status: str = "INACTIVE"
    isLinked: bool = False

class LicenseOut(LicenseInput):
    pass

def on_startup() -> None:
    init_db()

def api_ok(message: str = "ok") -> dict[str, str]:
    return {"message": message}

def row_json(row: dict[str, Any], key: str, default: Any) -> Any:
    return json_loads(row.get(key), default)

def product_row_to_model(row: dict[str, Any]) -> ProductOut:
    stock = to_int(row["stock"])
    low_stock = to_int(row["low_stock_alert"])
    if stock <= 0:
        stock_status = StockStatus.OUT_OF_STOCK
    elif stock <= low_stock:
        stock_status = StockStatus.LOW_STOCK
    else:
        stock_status = StockStatus.IN_STOCK
    return ProductOut(
        id=row["id"],
        reference=row["reference"],
        name=row["name"],
        category=row["category"],
        purchasePrice=to_money(row["purchase_price"]),
        salePrice=to_money(row["sale_price"]),
        semiWholesalePrice=to_money(row["semi_wholesale_price"]),
        wholesalePrice=to_money(row["wholesale_price"]),
        stock=stock,
        sku=row["sku"],
        imagePath=row["image_path"],
        barcode=row["barcode"],
        lowStockAlert=low_stock,
        packaging=row["packaging"],
        expirationDate=row["expiration_date"],
        specifications=[ProductSpecification(**item) for item in row_json(row, "specifications_json", [])],
        storageLocation=StorageLocation(**row_json(row, "storage_location_json", {})),
        variants=[ProductVariant(**item) for item in row_json(row, "variants_json", [])],
        stockStatus=stock_status,
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )

def category_row_to_model(row: dict[str, Any]) -> CategoryOut:
    return CategoryOut(
        id=row["id"],
        name=row["name"],
        iconKey=row["icon_key"],
        colorHex=row["color_hex"],
        imagePath=row["image_path"],
        type=CategoryType(row["type"]),
        parentId=row["parent_id"],
        active=as_bool(row["active"]),
        systemKey=row["system_key"],
    )

def expense_row_to_model(row: dict[str, Any]) -> ExpenseOut:
    return ExpenseOut(
        id=row["id"],
        date=row["date"],
        title=row["title"],
        category=row["category"],
        amount=to_money(row["amount"]),
        operationType=ExpenseOperationType(row["operation_type"]),
        paymentMethod=ExpensePaymentMethod(row["payment_method"]),
        status=ExpenseStatus(row["status"]),
        employeeName=row["employee_name"],
        note=row["note"],
    )

def customer_row_to_model(row: dict[str, Any]) -> CustomerOut:
    return CustomerOut(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        email=row["email"],
        city=row["city"],
        memberSince=row["member_since"],
        totalPurchases=to_money(row["total_purchases"]),
        debt=to_money(row["debt"]),
        isActive=as_bool(row["is_active"]),
        lastPayment=row["last_payment"],
        lastInvoice=row["last_invoice"],
    )

def employee_row_to_model(row: dict[str, Any]) -> EmployeeOut:
    password_hash = row.get("password_hash") or ""
    password_salt = row.get("password_salt") or ""
    employee_code = row.get("employee_code") or ""
    if not employee_code:
        employee_code = f"EMP-{int(row['id']):03d}"
    return EmployeeOut(
        id=row["id"],
        employeeCode=employee_code,
        fullName=row["full_name"],
        role=row.get("role") or "STAFF",
        username=row.get("username") or "",
        passwordHash=password_hash,
        passwordSalt=password_salt,
        department=row.get("department") or "General",
        phone=row.get("phone") or "",
        salary=to_money(row.get("salary")),
        active=as_bool(row.get("active", 1)),
        onLeave=as_bool(row.get("on_leave", 0)),
        createdAt=row.get("created_at") or "",
        hasPassword=bool(password_hash and password_salt),
    )

def repair_row_to_model(row: dict[str, Any]) -> RepairOut:
    parts = [RepairPart(**item) for item in row_json(row, "parts_json", [])]
    parts_total = sum(part.price for part in parts)
    total_price = to_money(row["price"]) + parts_total
    return RepairOut(
        id=row["id"],
        customerName=row["customer_name"],
        phone=row["phone"],
        device=row["device"],
        color=row["color"],
        imeiOrSerial=row["imei_or_serial"],
        issue=row["issue"],
        parts=parts,
        technician=row["technician"],
        price=to_money(row["price"]),
        paymentMethod=PaymentMethod(row["payment_method"]),
        paid=as_bool(row["paid"]),
        status=RepairStatus(row["status"]),
        date=row["date"],
        includedItems=row["included_items"],
        trackingCode=row["tracking_code"],
        syncState=RepairSyncState(row["sync_state"]),
        partsTotal=parts_total,
        totalPrice=total_price,
    )

def settings_row_to_model(row: dict[str, Any]) -> StoreSettingsOut:
    return StoreSettingsOut(
        storeName=row["store_name"],
        phone1=row["phone1"],
        phone2=row["phone2"],
        address=row["address"],
        social1=row["social1"],
        social2=row["social2"],
        logoPath=row["logo_path"],
        defaultPrinter=row["default_printer"],
        labelWidthMm=row["label_width_mm"],
        labelHeightMm=row["label_height_mm"],
        labelStoreNameX=row["label_store_name_x"],
        labelStoreNameY=row["label_store_name_y"],
        labelProductNameX=row["label_product_name_x"],
        labelProductNameY=row["label_product_name_y"],
        labelSkuX=row["label_sku_x"],
        labelSkuY=row["label_sku_y"],
        labelPriceX=row["label_price_x"],
        labelPriceY=row["label_price_y"],
        labelStoreNameColor=row["label_store_name_color"],
        labelProductNameColor=row["label_product_name_color"],
        labelSkuColor=row["label_sku_color"],
        labelPriceColor=row["label_price_color"],
        labelBarcodeX=row["label_barcode_x"],
        labelBarcodeY=row["label_barcode_y"],
        themeMode=row["theme_mode"],
        cashSoundMode=row["cash_sound_mode"],
        customCashSoundPath=row["custom_cash_sound_path"],
        chargilyApiKey=row["chargily_api_key"],
        receiptLanguage=row["receipt_language"],
        repairIncludedItems=row["repair_included_items"],
    )

def license_row_to_model(row: dict[str, Any]) -> LicenseOut:
    return LicenseOut(
        activationCode=row["activation_code"],
        deviceHash=row["device_hash"],
        activatedAt=row["activated_at"],
        lastValidatedAt=row["last_validated_at"],
        status=row["status"],
        isLinked=as_bool(row["is_linked"]),
    )

def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [row_to_dict(row) for row in rows if row is not None]

def fetch_one(query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        return row_to_dict(row)

def execute(query: str, params: Iterable[Any] = ()) -> int:
    with get_connection() as conn:
        cursor = conn.execute(query, tuple(params))
        return cursor.lastrowid

def unique_invoice_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"INV-{stamp}"

def invoice_items_for_invoice(invoice_id: int) -> list[InvoiceItemOut]:
    items = fetch_all("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (invoice_id,))
    return [
        InvoiceItemOut(
            id=item["id"],
            invoiceId=item["invoice_id"],
            name=item["name"],
            sku=item["sku"],
            qty=item["qty"],
            unitPrice=to_money(item["unit_price"]),
            unitCostSnapshot=to_money(item["unit_cost_snapshot"]),
            lineType=SaleLineType(item["line_type"]),
            bundleId=item["bundle_id"],
        )
        for item in items
    ]

def invoice_row_to_model(row: dict[str, Any]) -> InvoiceOut:
    return InvoiceOut(
        id=row["id"],
        syncKey=row.get("sync_key") or row.get("invoice_number") or "",
        invoiceNumber=row["invoice_number"],
        customerName=row["customer_name"],
        customerPhone=row["customer_phone"],
        items=invoice_items_for_invoice(row["id"]),
        total=to_money(row["total"]),
        paymentMethod=PaymentMethod(row["payment_method"]),
        status=InvoiceStatus(row["status"]),
        dateTime=row["date_time"],
        sellerName=row["seller_name"],
    )

def adjust_stock(product_id: int, delta: int) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        new_stock = int(row["stock"]) + delta
        if new_stock < 0:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        conn.execute("UPDATE products SET stock = ?, updated_at = ? WHERE id = ?", (new_stock, utc_now(), product_id))

def home() -> dict[str, str]:
    return {"message": "ReparNova backend is running"}

def health_check() -> dict[str, str]:
    return {"status": "ok"}

def meta() -> dict[str, Any]:
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return {
        "status": "ok",
        "database": str(active_store_db_path()),
        "tables": [row["name"] for row in tables],
    }

def list_products(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    low_stock: bool | None = Query(default=None),
) -> list[ProductOut]:
    query = "SELECT * FROM products WHERE 1=1"
    params: list[Any] = []
    if q:
        query += " AND (name LIKE ? OR sku LIKE ? OR reference LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    if category:
        query += " AND category = ?"
        params.append(category)
    rows = fetch_all(f"{query} ORDER BY name COLLATE NOCASE", params)
    products = [product_row_to_model(row) for row in rows]
    if low_stock is True:
        products = [item for item in products if item.stockStatus != StockStatus.IN_STOCK]
    if low_stock is False:
        products = [item for item in products if item.stockStatus == StockStatus.IN_STOCK]
    return products

def get_product(product_id: int) -> ProductOut:
    row = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_row_to_model(row)

def create_product(payload: ProductCreate) -> ProductOut:
    now = utc_now()
    try:
        product_id = execute(
            """
            INSERT INTO products (
                reference, name, category, purchase_price, sale_price,
                semi_wholesale_price, wholesale_price, stock, sku, image_path, barcode,
                low_stock_alert, packaging, expiration_date, specifications_json,
                storage_location_json, variants_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.reference,
                payload.name,
                payload.category,
                payload.purchasePrice,
                payload.salePrice,
                payload.semiWholesalePrice,
                payload.wholesalePrice,
                payload.stock,
                payload.sku,
                payload.imagePath,
                payload.barcode,
                payload.lowStockAlert,
                payload.packaging,
                payload.expirationDate,
                json_dumps([item.model_dump() for item in payload.specifications]),
                json_dumps(payload.storageLocation.model_dump()),
                json_dumps([item.model_dump() for item in payload.variants]),
                now,
                now,
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create product: {exc}") from exc
    product = get_product(product_id)
    publish_store_event("products", "created", product.model_dump())
    return product

def update_product(product_id: int, payload: ProductCreate) -> ProductOut:
    current = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if current is None:
        raise HTTPException(status_code=404, detail="Product not found")
    with get_connection() as conn:
        try:
            conn.execute(
                """
                UPDATE products
                SET reference = ?, name = ?, category = ?, purchase_price = ?, sale_price = ?,
                    semi_wholesale_price = ?, wholesale_price = ?, stock = ?, sku = ?, image_path = ?,
                    barcode = ?, low_stock_alert = ?, packaging = ?, expiration_date = ?,
                    specifications_json = ?, storage_location_json = ?, variants_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.reference,
                    payload.name,
                    payload.category,
                    payload.purchasePrice,
                    payload.salePrice,
                    payload.semiWholesalePrice,
                    payload.wholesalePrice,
                    payload.stock,
                    payload.sku,
                    payload.imagePath,
                    payload.barcode,
                    payload.lowStockAlert,
                    payload.packaging,
                    payload.expirationDate,
                    json_dumps([item.model_dump() for item in payload.specifications]),
                    json_dumps(payload.storageLocation.model_dump()),
                    json_dumps([item.model_dump() for item in payload.variants]),
                    utc_now(),
                    product_id,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to update product: {exc}") from exc
    product = get_product(product_id)
    publish_store_event("products", "updated", product.model_dump())
    return product

def delete_product(product_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM products WHERE id = ?", (product_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    publish_store_event("products", "deleted", {"id": product_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def duplicate_product(product_id: int, payload: ProductDuplicateRequest | None = None) -> ProductOut:
    row = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    payload = payload or ProductDuplicateRequest()
    base_name = payload.name or f"{row['name']} (Copy)"
    base_sku = payload.sku or f"{row['sku']}-COPY"
    base_reference = payload.reference or row["reference"]
    return create_product(
        ProductCreate(
            reference=base_reference,
            name=base_name,
            category=row["category"],
            purchasePrice=to_money(row["purchase_price"]),
            salePrice=to_money(row["sale_price"]),
            semiWholesalePrice=to_money(row["semi_wholesale_price"]),
            wholesalePrice=to_money(row["wholesale_price"]),
            stock=to_int(row["stock"]),
            sku=base_sku,
            imagePath=row["image_path"],
            barcode=row["barcode"],
            lowStockAlert=to_int(row["low_stock_alert"]),
            packaging=row["packaging"],
            expirationDate=row["expiration_date"],
            specifications=[ProductSpecification(**item) for item in row_json(row, "specifications_json", [])],
            storageLocation=StorageLocation(**row_json(row, "storage_location_json", {})),
            variants=[ProductVariant(**item) for item in row_json(row, "variants_json", [])],
        )
    )

def list_storage_placements() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM storage_placements ORDER BY name COLLATE NOCASE")

def save_storage_placement(payload: StoragePlacementInput) -> dict[str, Any]:
    existing = fetch_one("SELECT * FROM storage_placements WHERE name = ?", (payload.name,))
    if existing is None:
        placement_id = execute(
            "INSERT INTO storage_placements (name, location_json) VALUES (?, ?)",
            (payload.name, json_dumps(payload.location.model_dump())),
        )
    else:
        placement_id = existing["id"]
        execute(
            "UPDATE storage_placements SET location_json = ? WHERE id = ?",
            (json_dumps(payload.location.model_dump()), placement_id),
        )
    placement = fetch_one("SELECT * FROM storage_placements WHERE id = ?", (placement_id,)) or {}
    publish_store_event("storage_placements", "upserted", placement)
    return placement

def delete_storage_placement(placement_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM storage_placements WHERE id = ?", (placement_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Storage placement not found")
    publish_store_event("storage_placements", "deleted", {"id": placement_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def list_product_bundles() -> list[ProductBundleOut]:
    rows = fetch_all("SELECT * FROM product_bundles ORDER BY id DESC")
    return [product_bundle_row_to_model(row) for row in rows]

def get_product_bundle(bundle_id: int) -> ProductBundleOut:
    row = fetch_one("SELECT * FROM product_bundles WHERE id = ?", (bundle_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return product_bundle_row_to_model(row)

def create_product_bundle(payload: ProductBundleCreate) -> ProductBundleOut:
    sync_key = payload.syncKey.strip() or payload.code.strip() or uuid.uuid4().hex
    code = payload.code.strip() or sync_key[:12].upper()
    items_json = json_dumps(serialize_bundle_items(payload.items))
    bundle_id = execute(
        """
        INSERT INTO product_bundles (name, code, sync_key, bundle_price, active, items_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """.strip(),
        (
            payload.name.strip(),
            code,
            sync_key,
            payload.bundlePrice,
            1 if payload.active else 0,
            items_json,
            utc_now(),
        ),
    )
    bundle = get_product_bundle(bundle_id)
    publish_store_event("product_bundles", "created", bundle.model_dump())
    return bundle

def update_product_bundle(bundle_id: int, payload: ProductBundleCreate) -> ProductBundleOut:
    current = fetch_one("SELECT * FROM product_bundles WHERE id = ?", (bundle_id,))
    if current is None:
        raise HTTPException(status_code=404, detail="Bundle not found")
    sync_key = (payload.syncKey.strip() or current.get("sync_key") or payload.code.strip() or uuid.uuid4().hex)
    code = payload.code.strip() or current.get("code") or sync_key[:12].upper()
    execute(
        """
        UPDATE product_bundles
        SET name = ?, code = ?, sync_key = ?, bundle_price = ?, active = ?, items_json = ?
        WHERE id = ?
        """.strip(),
        (
            payload.name.strip(),
            code,
            sync_key,
            payload.bundlePrice,
            1 if payload.active else 0,
            json_dumps(serialize_bundle_items(payload.items)),
            bundle_id,
        ),
    )
    bundle = get_product_bundle(bundle_id)
    publish_store_event("product_bundles", "updated", bundle.model_dump())
    return bundle

def delete_product_bundle(bundle_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM product_bundles WHERE id = ?", (bundle_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Bundle not found")
    publish_store_event("product_bundles", "deleted", {"id": bundle_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def list_spare_parts() -> list[SparePartOut]:
    rows = fetch_all("SELECT * FROM spare_parts ORDER BY id DESC")
    return [spare_part_row_to_model(row) for row in rows]

def get_spare_part(part_id: int) -> SparePartOut:
    row = fetch_one("SELECT * FROM spare_parts WHERE id = ?", (part_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Spare part not found")
    return spare_part_row_to_model(row)

def create_spare_part(payload: SparePartCreate) -> SparePartOut:
    sync_key = payload.syncKey.strip() or uuid.uuid4().hex
    part_id = execute(
        """
        INSERT INTO spare_parts (sync_key, name, type_model, placement, qty, purchase_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """.strip(),
        (
            sync_key,
            payload.name.strip(),
            payload.typeModel.strip(),
            payload.placement.strip(),
            max(0, int(payload.qty)),
            float(payload.purchasePrice),
            utc_now(),
        ),
    )
    part = get_spare_part(part_id)
    publish_store_event("spare_parts", "created", part.model_dump())
    return part

def update_spare_part(part_id: int, payload: SparePartCreate) -> SparePartOut:
    current = fetch_one("SELECT * FROM spare_parts WHERE id = ?", (part_id,))
    if current is None:
        raise HTTPException(status_code=404, detail="Spare part not found")
    sync_key = payload.syncKey.strip() or current.get("sync_key") or uuid.uuid4().hex
    execute(
        """
        UPDATE spare_parts
        SET sync_key = ?, name = ?, type_model = ?, placement = ?, qty = ?, purchase_price = ?
        WHERE id = ?
        """.strip(),
        (
            sync_key,
            payload.name.strip(),
            payload.typeModel.strip(),
            payload.placement.strip(),
            max(0, int(payload.qty)),
            float(payload.purchasePrice),
            part_id,
        ),
    )
    part = get_spare_part(part_id)
    publish_store_event("spare_parts", "updated", part.model_dump())
    return part

def delete_spare_part(part_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM spare_parts WHERE id = ?", (part_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Spare part not found")
    publish_store_event("spare_parts", "deleted", {"id": part_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def serialize_bundle_items(items: list[ProductBundleItemBase]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in items:
        quantity = max(0, to_int(item.quantity))
        if quantity <= 0:
            continue
        serialized.append(
            {
                "productId": to_int(item.productId),
                "productSku": item.productSku.strip(),
                "productSyncKey": item.productSyncKey.strip(),
                "quantity": quantity,
            }
        )
    return serialized

def product_bundle_row_to_model(row: dict[str, Any]) -> ProductBundleOut:
    raw_items = json_loads(row.get("items_json"), [])
    items = [bundle_item_to_out(item) for item in raw_items]
    return ProductBundleOut(
        id=row["id"],
        name=row.get("name") or "",
        code=row.get("code") or "",
        syncKey=row.get("sync_key") or row.get("code") or "",
        bundlePrice=to_money(row.get("bundle_price")),
        active=as_bool(row.get("active")),
        items=items,
        createdAt=row.get("created_at") or "",
    )

def bundle_item_to_out(item: dict[str, Any]) -> ProductBundleItemOut:
    product = resolve_product_for_bundle_item(item)
    product_id = product["id"] if product is not None else to_int(item.get("productId") or item.get("product_id"))
    product_name = product["name"] if product is not None else item.get("productName") or ""
    product_sku = product["sku"] if product is not None else item.get("productSku") or item.get("product_sku") or ""
    product_sync_key = product_sync_key_for_row(product) if product is not None else item.get("productSyncKey") or ""
    return ProductBundleItemOut(
        productId=product_id,
        productSku=product_sku,
        productSyncKey=product_sync_key,
        quantity=max(0, to_int(item.get("quantity"))),
        productName=product_name,
        purchasePrice=to_money(product.get("purchase_price")) if product is not None else to_money(item.get("purchasePrice")),
        salePrice=to_money(product.get("sale_price")) if product is not None else to_money(item.get("salePrice")),
        availableStock=to_int(product.get("stock")) if product is not None else to_int(item.get("availableStock")),
    )

def resolve_product_for_bundle_item(item: dict[str, Any]) -> dict[str, Any] | None:
    product_id = to_int(item.get("productId") or item.get("product_id"))
    if product_id > 0:
        row = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
        if row is not None:
            return row

    sync_key = (item.get("productSyncKey") or "").strip().lower()
    if sync_key:
        for product in fetch_all("SELECT * FROM products"):
            if product_sync_key_for_row(product) == sync_key:
                return product

    sku = (item.get("productSku") or item.get("product_sku") or "").strip().lower()
    if sku:
        return fetch_one("SELECT * FROM products WHERE lower(sku) = ?", (sku,))
    return None

def product_sync_key_for_row(row: dict[str, Any] | None) -> str:
    if row is None:
        return ""
    candidate = (
        row.get("sku")
        or row.get("reference")
        or row.get("name")
        or ""
    )
    return candidate.strip().lower()

def spare_part_row_to_model(row: dict[str, Any]) -> SparePartOut:
    return SparePartOut(
        id=row["id"],
        syncKey=row.get("sync_key") or "",
        name=row.get("name") or "",
        typeModel=row.get("type_model") or "",
        placement=row.get("placement") or "",
        qty=to_int(row.get("qty")),
        purchasePrice=to_money(row.get("purchase_price")),
        createdAt=row.get("created_at") or "",
    )

def list_categories() -> list[CategoryOut]:
    return [category_row_to_model(row) for row in fetch_all("SELECT * FROM categories ORDER BY name COLLATE NOCASE")]

def create_category(payload: CategoryCreate) -> CategoryOut:
    category_id = execute(
        """
        INSERT INTO categories (name, icon_key, color_hex, image_path, type, parent_id, active, system_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.name,
            payload.iconKey,
            payload.colorHex,
            payload.imagePath,
            payload.type.value,
            payload.parentId,
            1 if payload.active else 0,
            payload.systemKey,
        ),
    )
    row = fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if row is None:
        raise HTTPException(status_code=500, detail="Category creation failed")
    category = category_row_to_model(row)
    publish_store_event("categories", "created", category.model_dump())
    return category

def update_category(category_id: int, payload: CategoryCreate) -> CategoryOut:
    row = fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Category not found")
    execute(
        """
        UPDATE categories
        SET name = ?, icon_key = ?, color_hex = ?, image_path = ?, type = ?, parent_id = ?, active = ?, system_key = ?
        WHERE id = ?
        """,
        (
            payload.name,
            payload.iconKey,
            payload.colorHex,
            payload.imagePath,
            payload.type.value,
            payload.parentId,
            1 if payload.active else 0,
            payload.systemKey,
            category_id,
        ),
    )
    category = get_category(category_id)
    publish_store_event("categories", "updated", category.model_dump())
    return category

def get_category(category_id: int) -> CategoryOut:
    row = fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category_row_to_model(row)

def delete_category(category_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    publish_store_event("categories", "deleted", {"id": category_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def list_expenses() -> list[ExpenseOut]:
    return [expense_row_to_model(row) for row in fetch_all("SELECT * FROM expenses ORDER BY date DESC, id DESC")]

def create_expense(payload: ExpenseCreate) -> ExpenseOut:
    expense_id = execute(
        """
        INSERT INTO expenses (date, title, category, amount, operation_type, payment_method, status, employee_name, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.date,
            payload.title,
            payload.category,
            payload.amount,
            payload.operationType.value,
            payload.paymentMethod.value,
            payload.status.value,
            payload.employeeName,
            payload.note,
        ),
    )
    expense = get_expense(expense_id)
    publish_store_event("expenses", "created", expense.model_dump())
    return expense

def update_expense(expense_id: int, payload: ExpenseCreate) -> ExpenseOut:
    row = fetch_one("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    execute(
        """
        UPDATE expenses
        SET date = ?, title = ?, category = ?, amount = ?, operation_type = ?, payment_method = ?, status = ?,
            employee_name = ?, note = ?
        WHERE id = ?
        """,
        (
            payload.date,
            payload.title,
            payload.category,
            payload.amount,
            payload.operationType.value,
            payload.paymentMethod.value,
            payload.status.value,
            payload.employeeName,
            payload.note,
            expense_id,
        ),
    )
    expense = get_expense(expense_id)
    publish_store_event("expenses", "updated", expense.model_dump())
    return expense

def get_expense(expense_id: int) -> ExpenseOut:
    row = fetch_one("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense_row_to_model(row)

def delete_expense(expense_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    publish_store_event("expenses", "deleted", {"id": expense_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def export_expenses_csv() -> Response:
    expenses = list_expenses()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "date",
            "title",
            "category",
            "amount",
            "operationType",
            "paymentMethod",
            "status",
            "employeeName",
            "note",
        ]
    )
    for item in expenses:
        writer.writerow(
            [
                item.id,
                item.date,
                item.title,
                item.category,
                item.amount,
                item.operationType.value,
                item.paymentMethod.value,
                item.status.value,
                item.employeeName,
                item.note,
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )

def list_customers() -> list[CustomerOut]:
    return [customer_row_to_model(row) for row in fetch_all("SELECT * FROM customers ORDER BY name COLLATE NOCASE")]

def create_customer(payload: CustomerCreate) -> CustomerOut:
    member_since = payload.memberSince or utc_now()
    customer_id = execute(
        """
        INSERT INTO customers (
            name, phone, email, city, member_since, total_purchases, debt, is_active, last_payment, last_invoice
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.name,
            payload.phone,
            payload.email,
            payload.city,
            member_since,
            payload.totalPurchases,
            payload.debt,
            1 if payload.isActive else 0,
            payload.lastPayment,
            payload.lastInvoice,
        ),
    )
    customer = get_customer(customer_id)
    publish_store_event("customers", "created", customer.model_dump())
    return customer

def update_customer(customer_id: int, payload: CustomerCreate) -> CustomerOut:
    if fetch_one("SELECT 1 FROM customers WHERE id = ?", (customer_id,)) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    execute(
        """
        UPDATE customers
        SET name = ?, phone = ?, email = ?, city = ?, member_since = ?, total_purchases = ?, debt = ?,
            is_active = ?, last_payment = ?, last_invoice = ?
        WHERE id = ?
        """,
        (
            payload.name,
            payload.phone,
            payload.email,
            payload.city,
            payload.memberSince or utc_now(),
            payload.totalPurchases,
            payload.debt,
            1 if payload.isActive else 0,
            payload.lastPayment,
            payload.lastInvoice,
            customer_id,
        ),
    )
    customer = get_customer(customer_id)
    publish_store_event("customers", "updated", customer.model_dump())
    return customer

def get_customer(customer_id: int) -> CustomerOut:
    row = fetch_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_row_to_model(row)

def delete_customer(customer_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    publish_store_event("customers", "deleted", {"id": customer_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def list_employees() -> list[EmployeeOut]:
    return [
        employee_row_to_model(row)
        for row in fetch_all(
            """
            SELECT
                id,
                employee_code,
                full_name,
                role,
                username,
                password_hash,
                password_salt,
                department,
                phone,
                salary,
                active,
                on_leave,
                created_at
            FROM users
            ORDER BY id ASC
            """
        )
    ]

def get_employee(employee_id: int) -> EmployeeOut:
    row = fetch_one(
        """
        SELECT
            id,
            employee_code,
            full_name,
            role,
            username,
            password_hash,
            password_salt,
            department,
            phone,
            salary,
            active,
            on_leave,
            created_at
        FROM users
        WHERE id = ?
        LIMIT 1
        """,
        (employee_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee_row_to_model(row)

def create_employee(payload: EmployeeCreate) -> EmployeeOut:
    created_at = payload.createdAt or utc_now()
    employee_id = execute(
        """
        INSERT INTO users (
            employee_code,
            full_name,
            role,
            username,
            password_hash,
            password_salt,
            department,
            phone,
            salary,
            active,
            on_leave,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.employeeCode.strip(),
            payload.fullName.strip(),
            payload.role.strip().upper() or "STAFF",
            payload.username.strip().lower(),
            payload.passwordHash,
            payload.passwordSalt,
            payload.department.strip() or "General",
            payload.phone.strip(),
            to_money(payload.salary),
            1 if payload.active else 0,
            1 if payload.onLeave else 0,
            created_at,
        ),
    )
    if not payload.employeeCode.strip():
        execute("UPDATE users SET employee_code = ? WHERE id = ?", (f"EMP-{employee_id:03d}", employee_id))
    employee = get_employee(employee_id)
    publish_store_event("employees", "created", employee.model_dump())
    return employee

def update_employee(employee_id: int, payload: EmployeeUpdate) -> EmployeeOut:
    if fetch_one("SELECT 1 FROM users WHERE id = ?", (employee_id,)) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    execute(
        """
        UPDATE users SET
            employee_code = ?,
            full_name = ?,
            role = ?,
            username = ?,
            password_hash = ?,
            password_salt = ?,
            department = ?,
            phone = ?,
            salary = ?,
            active = ?,
            on_leave = ?,
            created_at = ?
        WHERE id = ?
        """,
        (
            payload.employeeCode.strip(),
            payload.fullName.strip(),
            payload.role.strip().upper() or "STAFF",
            payload.username.strip().lower(),
            payload.passwordHash,
            payload.passwordSalt,
            payload.department.strip() or "General",
            payload.phone.strip(),
            to_money(payload.salary),
            1 if payload.active else 0,
            1 if payload.onLeave else 0,
            payload.createdAt or utc_now(),
            employee_id,
        ),
    )
    employee = get_employee(employee_id)
    publish_store_event("employees", "updated", employee.model_dump())
    return employee

def delete_employee(employee_id: int) -> Response:
    employee = fetch_one("SELECT * FROM users WHERE id = ? LIMIT 1", (employee_id,))
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    execute("DELETE FROM users WHERE id = ?", (employee_id,))
    publish_store_event("employees", "deleted", row_to_dict(employee))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def list_invoices() -> list[InvoiceOut]:
    return [invoice_row_to_model(row) for row in fetch_all("SELECT * FROM invoices ORDER BY date_time DESC, id DESC")]

def get_invoice(invoice_number: str) -> InvoiceOut:
    row = fetch_one("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,))
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_row_to_model(row)

def persist_invoice(payload: InvoiceInput, sync_import: bool = False) -> InvoiceOut:
    if not payload.items:
        raise HTTPException(status_code=400, detail="Invoice must contain at least one item")
    invoice_number = payload.invoiceNumber.strip() or unique_invoice_number()
    sync_key = payload.syncKey.strip() or payload.invoiceNumber or uuid.uuid4().hex
    total = 0.0

    with get_connection() as conn:
        try:
            while conn.execute(
                "SELECT 1 FROM invoices WHERE invoice_number = ? LIMIT 1",
                (invoice_number,),
            ).fetchone() is not None:
                invoice_number = unique_invoice_number()

            for item in payload.items:
                if item.lineType == SaleLineType.PRODUCT:
                    product_row = conn.execute("SELECT id, stock, name, sku, sale_price, purchase_price FROM products WHERE sku = ?", (item.sku,)).fetchone()
                    if product_row is None:
                        if not sync_import:
                            raise HTTPException(status_code=400, detail=f"Product with SKU {item.sku} not found")
                    elif not sync_import and int(product_row["stock"]) < item.qty:
                        raise HTTPException(status_code=400, detail=f"Not enough stock for {item.name}")
                total += float(item.unitPrice) * int(item.qty)

            cursor = conn.execute(
                """
                INSERT INTO invoices (sync_key, invoice_number, customer_name, customer_phone, total, payment_method, status, date_time, seller_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sync_key,
                    invoice_number,
                    payload.customerName,
                    payload.customerPhone,
                    total,
                    payload.paymentMethod.value,
                    payload.status.value,
                    utc_now(),
                    payload.sellerName,
                ),
            )
            invoice_id = cursor.lastrowid

            for item in payload.items:
                conn.execute(
                    """
                    INSERT INTO invoice_items (
                        invoice_id, name, sku, qty, unit_price, unit_cost_snapshot, line_type, bundle_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id,
                        item.name,
                        item.sku,
                        item.qty,
                        item.unitPrice,
                        item.unitCostSnapshot,
                        item.lineType.value,
                        item.bundleId,
                    ),
                )
                if item.lineType == SaleLineType.PRODUCT:
                    conn.execute(
                        "UPDATE products SET stock = stock - ?, updated_at = ? WHERE sku = ?",
                        (item.qty, utc_now(), item.sku),
                    )

            if payload.customerName.strip():
                customer = conn.execute(
                    "SELECT id, total_purchases, debt FROM customers WHERE name = ? OR phone = ? ORDER BY id LIMIT 1",
                    (payload.customerName.strip(), payload.customerPhone.strip()),
                ).fetchone()
                if customer is None:
                    conn.execute(
                        """
                        INSERT INTO customers (name, phone, email, city, member_since, total_purchases, debt, is_active, last_payment, last_invoice)
                        VALUES (?, ?, '', '', ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            payload.customerName.strip(),
                            payload.customerPhone.strip(),
                            utc_now(),
                            total,
                            total if payload.paymentMethod == PaymentMethod.CREDIT else 0,
                            payload.paymentMethod.value,
                            invoice_number,
                        ),
                    )
                else:
                    debt_delta = total if payload.paymentMethod == PaymentMethod.CREDIT else 0
                    conn.execute(
                        """
                        UPDATE customers
                        SET total_purchases = total_purchases + ?, debt = debt + ?, last_payment = ?, last_invoice = ?
                        WHERE id = ?
                        """,
                        (total, debt_delta, payload.paymentMethod.value, invoice_number, customer["id"]),
                    )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    invoice = get_invoice(invoice_number)
    publish_store_event("invoices", "created", invoice.model_dump())
    return invoice

def create_invoice(
    payload: InvoiceInput,
    sync_import: bool = Header(False, alias="X-Sync-Import"),
) -> InvoiceOut:
    return persist_invoice(payload, sync_import=sync_import)

def update_invoice(invoice_number: str, payload: InvoiceEditInput) -> InvoiceOut:
    row = fetch_one("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,))
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    execute(
        """
        UPDATE invoices
        SET customer_name = ?, customer_phone = ?, payment_method = ?, status = ?
        WHERE invoice_number = ?
        """,
        (payload.customerName, payload.customerPhone, payload.paymentMethod.value, payload.status.value, invoice_number),
    )
    invoice = get_invoice(invoice_number)
    publish_store_event("invoices", "updated", invoice.model_dump())
    return invoice

def cancel_invoice(invoice_number: str) -> InvoiceOut:
    with get_connection() as conn:
        invoice = conn.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,)).fetchone()
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice["status"] == InvoiceStatus.CANCELLED.value:
            return invoice_row_to_model(row_to_dict(invoice))
        items = conn.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice["id"],)).fetchall()
        for item in items:
            if item["line_type"] == SaleLineType.PRODUCT.value:
                conn.execute("UPDATE products SET stock = stock + ?, updated_at = ? WHERE sku = ?", (item["qty"], utc_now(), item["sku"]))
        conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (InvoiceStatus.CANCELLED.value, invoice["id"]))
    invoice = get_invoice(invoice_number)
    publish_store_event("invoices", "cancelled", invoice.model_dump())
    return invoice

def list_refunds() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM refunds ORDER BY created_at DESC") if table_exists("refunds") else []

def table_exists(name: str) -> bool:
    row = fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,))
    return row is not None

def list_repairs() -> list[RepairOut]:
    return [repair_row_to_model(row) for row in fetch_all("SELECT * FROM repairs ORDER BY date DESC, id DESC")]

def get_repair(repair_id: int) -> RepairOut:
    row = fetch_one("SELECT * FROM repairs WHERE id = ?", (repair_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Repair not found")
    return repair_row_to_model(row)

def create_repair(payload: RepairCreate) -> RepairOut:
    repair_id = execute(
        """
        INSERT INTO repairs (
            customer_name, phone, device, color, imei_or_serial, issue, parts_json, technician, price,
            payment_method, paid, status, date, included_items, tracking_code, sync_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.customerName,
            payload.phone,
            payload.device,
            payload.color,
            payload.imeiOrSerial,
            payload.issue,
            json_dumps([part.model_dump() for part in payload.parts]),
            payload.technician,
            payload.price,
            payload.paymentMethod.value,
            1 if payload.paid else 0,
            payload.status.value,
            payload.date,
            payload.includedItems,
            payload.trackingCode,
            payload.syncState.value,
        ),
    )
    execute(
        """
        INSERT INTO repair_timeline_events (repair_id, status, changed_at, employee_name, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (repair_id, payload.status.value, utc_now(), payload.technician, "Repair created"),
    )
    repair = get_repair(repair_id)
    publish_store_event("repairs", "created", repair.model_dump())
    return repair

def update_repair(repair_id: int, payload: RepairCreate) -> RepairOut:
    if fetch_one("SELECT 1 FROM repairs WHERE id = ?", (repair_id,)) is None:
        raise HTTPException(status_code=404, detail="Repair not found")
    execute(
        """
        UPDATE repairs
        SET customer_name = ?, phone = ?, device = ?, color = ?, imei_or_serial = ?, issue = ?, parts_json = ?,
            technician = ?, price = ?, payment_method = ?, paid = ?, status = ?, date = ?, included_items = ?,
            tracking_code = ?, sync_state = ?
        WHERE id = ?
        """,
        (
            payload.customerName,
            payload.phone,
            payload.device,
            payload.color,
            payload.imeiOrSerial,
            payload.issue,
            json_dumps([part.model_dump() for part in payload.parts]),
            payload.technician,
            payload.price,
            payload.paymentMethod.value,
            1 if payload.paid else 0,
            payload.status.value,
            payload.date,
            payload.includedItems,
            payload.trackingCode,
            payload.syncState.value,
            repair_id,
        ),
    )
    repair = get_repair(repair_id)
    publish_store_event("repairs", "updated", repair.model_dump())
    return repair

def update_repair_status(repair_id: int, payload: RepairStatusUpdate) -> RepairOut:
    if fetch_one("SELECT 1 FROM repairs WHERE id = ?", (repair_id,)) is None:
        raise HTTPException(status_code=404, detail="Repair not found")
    execute(
        "UPDATE repairs SET status = ?, sync_state = ? WHERE id = ?",
        (payload.status.value, RepairSyncState.SYNCED.value, repair_id),
    )
    execute(
        """
        INSERT INTO repair_timeline_events (repair_id, status, changed_at, employee_name, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (repair_id, payload.status.value, utc_now(), payload.employeeName, payload.note),
    )
    repair = get_repair(repair_id)
    publish_store_event("repairs", "status_changed", repair.model_dump())
    return repair

def delete_repair(repair_id: int) -> Response:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM repairs WHERE id = ?", (repair_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Repair not found")
    publish_store_event("repairs", "deleted", {"id": repair_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def get_settings() -> StoreSettingsOut:
    row = fetch_one("SELECT * FROM store_settings WHERE id = 1")
    if row is None:
        raise HTTPException(status_code=500, detail="Settings row missing")
    return settings_row_to_model(row)

def update_settings(payload: StoreSettingsInput) -> StoreSettingsOut:
    execute(
        """
        UPDATE store_settings SET
            store_name = ?, phone1 = ?, phone2 = ?, address = ?, social1 = ?, social2 = ?, logo_path = ?,
            default_printer = ?, label_width_mm = ?, label_height_mm = ?, label_store_name_x = ?,
            label_store_name_y = ?, label_product_name_x = ?, label_product_name_y = ?, label_sku_x = ?,
            label_sku_y = ?, label_price_x = ?, label_price_y = ?, label_store_name_color = ?,
            label_product_name_color = ?, label_sku_color = ?, label_price_color = ?, label_barcode_x = ?,
            label_barcode_y = ?, theme_mode = ?, cash_sound_mode = ?, custom_cash_sound_path = ?,
            chargily_api_key = ?, receipt_language = ?, repair_included_items = ?
        WHERE id = 1
        """,
        (
            payload.storeName,
            payload.phone1,
            payload.phone2,
            payload.address,
            payload.social1,
            payload.social2,
            payload.logoPath,
            payload.defaultPrinter,
            payload.labelWidthMm,
            payload.labelHeightMm,
            payload.labelStoreNameX,
            payload.labelStoreNameY,
            payload.labelProductNameX,
            payload.labelProductNameY,
            payload.labelSkuX,
            payload.labelSkuY,
            payload.labelPriceX,
            payload.labelPriceY,
            payload.labelStoreNameColor,
            payload.labelProductNameColor,
            payload.labelSkuColor,
            payload.labelPriceColor,
            payload.labelBarcodeX,
            payload.labelBarcodeY,
            payload.themeMode,
            payload.cashSoundMode,
            payload.customCashSoundPath,
            payload.chargilyApiKey,
            payload.receiptLanguage,
            payload.repairIncludedItems,
        ),
    )
    settings = get_settings()
    publish_store_event("settings", "updated", settings.model_dump())
    return settings

def get_license() -> LicenseOut:
    row = fetch_one("SELECT * FROM licenses WHERE id = 1")
    if row is None:
        raise HTTPException(status_code=500, detail="License row missing")
    return license_row_to_model(row)

def update_license(payload: LicenseInput) -> LicenseOut:
    execute(
        """
        UPDATE licenses SET activation_code = ?, device_hash = ?, activated_at = ?, last_validated_at = ?,
            status = ?, is_linked = ?
        WHERE id = 1
        """,
        (
            payload.activationCode,
            payload.deviceHash,
            payload.activatedAt,
            payload.lastValidatedAt,
            payload.status,
            1 if payload.isLinked else 0,
        ),
    )
    license_record = get_license()
    publish_store_event("license", "updated", license_record.model_dump())
    return license_record

def analytics() -> AnalyticsSnapshotOut:
    products = fetch_all("SELECT stock, low_stock_alert, purchase_price, sale_price FROM products")
    customers = fetch_one("SELECT COUNT(*) AS count FROM customers WHERE is_active = 1") or {"count": 0}
    employees = fetch_one("SELECT COUNT(*) AS count FROM users WHERE active = 1") or {"count": 0}
    expenses = fetch_one("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE status != 'CANCELLED'") or {"total": 0}
    sales = fetch_one("SELECT COALESCE(SUM(total), 0) AS total FROM invoices WHERE status = 'COMPLETED'") or {"total": 0}
    low_stock = sum(1 for product in products if int(product["stock"]) <= int(product["low_stock_alert"]))
    purchases_total = sum(to_money(product["purchase_price"]) * max(int(product["stock"]), 0) for product in products)
    net_profit = to_money(sales["total"]) - to_money(expenses["total"])
    return AnalyticsSnapshotOut(
        sales=to_money(sales["total"]),
        lowStockItems=low_stock,
        customersCount=int(customers["count"]),
        netProfit=net_profit,
        purchases=purchases_total,
        expenses=to_money(expenses["total"]),
        employeesCount=int(employees["count"]),
    )

def debug_reset() -> dict[str, str]:
    return api_ok("debug endpoint disabled")
