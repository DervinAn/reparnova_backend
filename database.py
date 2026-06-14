from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Iterator


BASE_DIR = Path(__file__).resolve().parent
STORES_DIR = BASE_DIR / "stores"
DB_PATH = Path(os.getenv("REPARNOVA_DB_PATH", BASE_DIR / "reparnova.db")).expanduser()
MASTER_DB_PATH = Path(os.getenv("REPARNOVA_MASTER_DB_PATH", BASE_DIR / "reparnova_master.db")).expanduser()

_DB_LOCK = Lock()
_ACTIVE_DB_PATH: ContextVar[Path] = ContextVar("reparnova_active_db_path", default=DB_PATH)
_ACTIVE_STORE: ContextVar[dict[str, Any] | None] = ContextVar("reparnova_active_store", default=None)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = _connect(_ACTIVE_DB_PATH.get())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


@contextmanager
def get_master_connection() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = _connect(MASTER_DB_PATH)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def set_active_store_db_path(path: Path) -> None:
    _ACTIVE_DB_PATH.set(path)


def active_store_db_path() -> Path:
    return _ACTIVE_DB_PATH.get()


def set_active_store(store: dict[str, Any] | None) -> None:
    _ACTIVE_STORE.set(store)


def active_store() -> dict[str, Any] | None:
    return _ACTIVE_STORE.get()


def default_store_db_path() -> Path:
    return DB_PATH


def store_db_path_for_code(code: str) -> Path:
    safe_code = "".join(ch for ch in code.lower().strip() if ch.isalnum() or ch in {"-", "_"})
    if not safe_code:
        safe_code = "store"
    return STORES_DIR / f"{safe_code}.db"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_loads(value: str | bytes | None, default: Any) -> Any:
    if value in (None, "", b""):
        return default
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def store_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            purchase_price REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            semi_wholesale_price REAL NOT NULL DEFAULT 0,
            wholesale_price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            sku TEXT NOT NULL UNIQUE,
            image_path TEXT NOT NULL DEFAULT '',
            barcode TEXT NOT NULL DEFAULT '',
            low_stock_alert INTEGER NOT NULL DEFAULT 5,
            packaging TEXT NOT NULL DEFAULT '',
            expiration_date TEXT NOT NULL DEFAULT '',
            specifications_json TEXT NOT NULL DEFAULT '[]',
            storage_location_json TEXT NOT NULL DEFAULT '{}',
            variants_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS product_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            sync_key TEXT NOT NULL DEFAULT '',
            bundle_price REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            items_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS storage_placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            location_json TEXT NOT NULL DEFAULT '{}'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS spare_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_key TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            type_model TEXT NOT NULL DEFAULT '',
            placement TEXT NOT NULL DEFAULT '',
            qty INTEGER NOT NULL DEFAULT 0,
            purchase_price REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            icon_key TEXT NOT NULL DEFAULT '',
            color_hex TEXT NOT NULL DEFAULT '#111827',
            image_path TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL DEFAULT 'PRODUCT',
            parent_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            system_key TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            operation_type TEXT NOT NULL DEFAULT 'EXPENSE',
            payment_method TEXT NOT NULL DEFAULT 'CASH',
            status TEXT NOT NULL DEFAULT 'PAID',
            employee_name TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            member_since TEXT NOT NULL,
            total_purchases REAL NOT NULL DEFAULT 0,
            debt REAL NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_payment TEXT NOT NULL DEFAULT '',
            last_invoice TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS customer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'CASH',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_key TEXT NOT NULL DEFAULT '',
            invoice_number TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL DEFAULT '',
            customer_phone TEXT NOT NULL DEFAULT '',
            total REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'CASH',
            status TEXT NOT NULL DEFAULT 'COMPLETED',
            date_time TEXT NOT NULL,
            seller_name TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sku TEXT NOT NULL DEFAULT '',
            qty INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL DEFAULT 0,
            unit_cost_snapshot REAL NOT NULL DEFAULT 0,
            line_type TEXT NOT NULL DEFAULT 'PRODUCT',
            bundle_id INTEGER,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            device TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '',
            imei_or_serial TEXT NOT NULL DEFAULT '',
            issue TEXT NOT NULL DEFAULT '',
            parts_json TEXT NOT NULL DEFAULT '[]',
            technician TEXT NOT NULL DEFAULT '',
            price REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'CASH',
            paid INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'RECEIVED',
            date TEXT NOT NULL,
            included_items TEXT NOT NULL DEFAULT '',
            tracking_code TEXT NOT NULL DEFAULT '',
            sync_state TEXT NOT NULL DEFAULT 'PENDING'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repair_timeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            employee_name TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(repair_id) REFERENCES repairs(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS store_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            store_name TEXT NOT NULL DEFAULT '',
            phone1 TEXT NOT NULL DEFAULT '',
            phone2 TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            social1 TEXT NOT NULL DEFAULT '',
            social2 TEXT NOT NULL DEFAULT '',
            logo_path TEXT NOT NULL DEFAULT '',
            default_printer TEXT NOT NULL DEFAULT '',
            label_width_mm INTEGER NOT NULL DEFAULT 40,
            label_height_mm INTEGER NOT NULL DEFAULT 20,
            label_store_name_x REAL NOT NULL DEFAULT 0.10,
            label_store_name_y REAL NOT NULL DEFAULT 0.14,
            label_product_name_x REAL NOT NULL DEFAULT 0.10,
            label_product_name_y REAL NOT NULL DEFAULT 0.30,
            label_sku_x REAL NOT NULL DEFAULT 0.10,
            label_sku_y REAL NOT NULL DEFAULT 0.44,
            label_price_x REAL NOT NULL DEFAULT 0.10,
            label_price_y REAL NOT NULL DEFAULT 0.88,
            label_store_name_color TEXT NOT NULL DEFAULT '#111827',
            label_product_name_color TEXT NOT NULL DEFAULT '#111827',
            label_sku_color TEXT NOT NULL DEFAULT '#64748B',
            label_price_color TEXT NOT NULL DEFAULT '#111827',
            label_barcode_x REAL NOT NULL DEFAULT 0.08,
            label_barcode_y REAL NOT NULL DEFAULT 0.54,
            theme_mode TEXT NOT NULL DEFAULT 'DARK',
            cash_sound_mode TEXT NOT NULL DEFAULT 'DEFAULT',
            custom_cash_sound_path TEXT NOT NULL DEFAULT '',
            chargily_api_key TEXT NOT NULL DEFAULT '',
            receipt_language TEXT NOT NULL DEFAULT 'AR',
            repair_included_items TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            activation_code TEXT NOT NULL DEFAULT '',
            device_hash TEXT NOT NULL DEFAULT '',
            activated_at TEXT NOT NULL DEFAULT '',
            last_validated_at TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'INACTIVE',
            is_linked INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'admin',
            password_hash TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """,
    ]


def master_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            db_path TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            device_limit INTEGER NOT NULL DEFAULT 2,
            license_key TEXT NOT NULL DEFAULT '',
            license_status TEXT NOT NULL DEFAULT 'INACTIVE',
            license_activated_at TEXT NOT NULL DEFAULT '',
            license_deactivated_at TEXT NOT NULL DEFAULT '',
            license_expires_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'desktop',
            device_key TEXT NOT NULL UNIQUE,
            device_fingerprint TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            requested_at TEXT NOT NULL DEFAULT '',
            approved_at TEXT NOT NULL DEFAULT '',
            last_seen TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )
        """,
    ]


def init_store_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        for statement in store_schema_statements():
            conn.execute(statement)
        conn.execute(
            "INSERT OR IGNORE INTO store_settings (id, store_name) VALUES (1, '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO licenses (id, activation_code) VALUES (1, '')"
        )
        _ensure_store_user_columns(conn)
        _ensure_store_invoice_columns(conn)
        _ensure_store_bundle_columns(conn)
        _ensure_store_spare_part_columns(conn)


def init_master_db() -> None:
    with get_master_connection() as conn:
        for statement in master_schema_statements():
            conn.execute(statement)
        _ensure_master_store_columns(conn)
        _ensure_master_device_columns(conn)


def _ensure_master_store_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(stores)").fetchall()}
    migrations = [
        ("license_key", "TEXT NOT NULL DEFAULT ''"),
        ("license_status", "TEXT NOT NULL DEFAULT 'INACTIVE'"),
        ("license_activated_at", "TEXT NOT NULL DEFAULT ''"),
        ("license_deactivated_at", "TEXT NOT NULL DEFAULT ''"),
        ("license_expires_at", "TEXT NOT NULL DEFAULT ''"),
        ("device_limit", "INTEGER NOT NULL DEFAULT 2"),
    ]
    for column_name, column_sql in migrations:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE stores ADD COLUMN {column_name} {column_sql}")

    conn.execute("UPDATE stores SET license_key = COALESCE(license_key, '') WHERE license_key IS NULL")
    conn.execute("UPDATE stores SET license_status = COALESCE(license_status, 'INACTIVE') WHERE license_status IS NULL OR license_status = ''")
    conn.execute("UPDATE stores SET license_activated_at = COALESCE(license_activated_at, '') WHERE license_activated_at IS NULL")
    conn.execute("UPDATE stores SET license_deactivated_at = COALESCE(license_deactivated_at, '') WHERE license_deactivated_at IS NULL")
    conn.execute("UPDATE stores SET license_expires_at = COALESCE(license_expires_at, '') WHERE license_expires_at IS NULL")
    conn.execute("UPDATE stores SET device_limit = COALESCE(device_limit, 2) WHERE device_limit IS NULL OR device_limit <= 0")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_stores_license_key ON stores(license_key) WHERE license_key <> ''"
    )


def _ensure_master_device_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    migrations = [
        ("device_fingerprint", "TEXT NOT NULL DEFAULT ''"),
        ("requested_at", "TEXT NOT NULL DEFAULT ''"),
        ("approved_at", "TEXT NOT NULL DEFAULT ''"),
    ]
    for column_name, column_sql in migrations:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE devices ADD COLUMN {column_name} {column_sql}")

    conn.execute("UPDATE devices SET device_fingerprint = COALESCE(device_fingerprint, '') WHERE device_fingerprint IS NULL")
    conn.execute("UPDATE devices SET requested_at = COALESCE(requested_at, '') WHERE requested_at IS NULL")
    conn.execute("UPDATE devices SET approved_at = COALESCE(approved_at, '') WHERE approved_at IS NULL")


def init_db() -> None:
    init_master_db()
    init_store_db(DB_PATH)
    ensure_default_store()


def _ensure_store_user_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    migrations = [
        ("employee_code", "TEXT NOT NULL DEFAULT ''"),
        ("password_salt", "TEXT NOT NULL DEFAULT ''"),
        ("department", "TEXT NOT NULL DEFAULT 'General'"),
        ("phone", "TEXT NOT NULL DEFAULT ''"),
        ("salary", "REAL NOT NULL DEFAULT 0"),
        ("on_leave", "INTEGER NOT NULL DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ]
    for column_name, column_sql in migrations:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_sql}")

    conn.execute("UPDATE users SET employee_code = COALESCE(employee_code, '') WHERE employee_code IS NULL")
    conn.execute("UPDATE users SET password_salt = COALESCE(password_salt, '') WHERE password_salt IS NULL")
    conn.execute("UPDATE users SET department = COALESCE(department, 'General') WHERE department IS NULL OR department = ''")
    conn.execute("UPDATE users SET phone = COALESCE(phone, '') WHERE phone IS NULL")
    conn.execute("UPDATE users SET salary = COALESCE(salary, 0) WHERE salary IS NULL")
    conn.execute("UPDATE users SET on_leave = COALESCE(on_leave, 0) WHERE on_leave IS NULL")
    conn.execute("UPDATE users SET created_at = COALESCE(created_at, '') WHERE created_at IS NULL")
    conn.execute(
        "UPDATE users SET employee_code = printf('EMP-%03d', id) WHERE employee_code IS NULL OR trim(employee_code) = ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_code ON users(employee_code) WHERE employee_code <> ''"
    )


def _ensure_store_invoice_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()}
    if "sync_key" not in existing_columns:
        conn.execute("ALTER TABLE invoices ADD COLUMN sync_key TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE invoices SET sync_key = COALESCE(sync_key, '') WHERE sync_key IS NULL")
    conn.execute(
        "UPDATE invoices SET sync_key = invoice_number WHERE trim(COALESCE(sync_key, '')) = '' AND trim(COALESCE(invoice_number, '')) <> ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_sync_key ON invoices(sync_key) WHERE sync_key <> ''"
    )


def _ensure_store_bundle_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(product_bundles)").fetchall()}
    migrations = [
        ("sync_key", "TEXT NOT NULL DEFAULT ''"),
        ("items_json", "TEXT NOT NULL DEFAULT '[]'"),
    ]
    for column_name, column_sql in migrations:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE product_bundles ADD COLUMN {column_name} {column_sql}")

    conn.execute("UPDATE product_bundles SET sync_key = COALESCE(sync_key, '') WHERE sync_key IS NULL")
    conn.execute(
        "UPDATE product_bundles SET sync_key = COALESCE(NULLIF(sync_key, ''), code) WHERE trim(COALESCE(sync_key, '')) = ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_product_bundles_sync_key ON product_bundles(sync_key) WHERE sync_key <> ''"
    )


def _ensure_store_spare_part_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(spare_parts)").fetchall()}
    migrations = [
        ("sync_key", "TEXT NOT NULL DEFAULT ''"),
        ("type_model", "TEXT NOT NULL DEFAULT ''"),
        ("placement", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ]
    for column_name, column_sql in migrations:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE spare_parts ADD COLUMN {column_name} {column_sql}")

    conn.execute("UPDATE spare_parts SET sync_key = COALESCE(sync_key, '') WHERE sync_key IS NULL")
    conn.execute(
        "UPDATE spare_parts SET sync_key = lower(hex(randomblob(16))) WHERE trim(COALESCE(sync_key, '')) = ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_spare_parts_sync_key ON spare_parts(sync_key) WHERE sync_key <> ''"
    )


def ensure_default_store() -> dict[str, Any]:
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE code = ?", ("default",)).fetchone()
        if row is None:
            db_path = str(DB_PATH)
            license_key = f"LIC-{uuid.uuid4().hex[:12].upper()}"
            conn.execute(
                """
                INSERT INTO stores (code, name, phone, address, db_path, active, device_limit, license_key, license_status, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 2, ?, 'ACTIVE', datetime('now'))
                """,
                ("default", "Default Store", "", "", db_path, license_key),
            )
            row = conn.execute("SELECT * FROM stores WHERE code = ?", ("default",)).fetchone()
    return row_to_dict(row) or {}


def list_stores() -> list[dict[str, Any]]:
    with get_master_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                stores.*,
                COALESCE(device_counts.device_count, 0) AS device_count,
                COALESCE(pending_counts.pending_device_count, 0) AS pending_device_count
            FROM stores
            LEFT JOIN (
                SELECT store_id, COUNT(*) AS device_count
                FROM devices
                WHERE active = 1
                GROUP BY store_id
            ) AS device_counts ON device_counts.store_id = stores.id
            LEFT JOIN (
                SELECT store_id, COUNT(*) AS pending_device_count
                FROM devices
                WHERE active = 0
                GROUP BY store_id
            ) AS pending_counts ON pending_counts.store_id = stores.id
            WHERE stores.code <> 'default'
            ORDER BY stores.id
            """
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        if row is None:
            continue
        payload = row_to_dict(row) or {}
        payload["device_count"] = int(payload.get("device_count") or 0)
        payload["pending_device_count"] = int(payload.get("pending_device_count") or 0)
        result.append(payload)
    return result


def get_store_by_id(store_id: int) -> dict[str, Any] | None:
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    return row_to_dict(row)


def get_store_by_code(code: str) -> dict[str, Any] | None:
    normalized = code.strip().lower()
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE lower(code) = ?", (normalized,)).fetchone()
    return row_to_dict(row)


def get_store_by_db_path(db_path: Path | str) -> dict[str, Any] | None:
    path_value = str(Path(db_path))
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE db_path = ?", (path_value,)).fetchone()
    return row_to_dict(row)


def get_store_by_license_key(license_key: str) -> dict[str, Any] | None:
    normalized = license_key.strip().upper()
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE upper(license_key) = ?", (normalized,)).fetchone()
    return row_to_dict(row)


def create_store(
    name: str,
    phone: str = "",
    address: str = "",
    code: str | None = None,
    device_limit: int = 2,
) -> dict[str, Any]:
    store_code = code or generate_store_code(name)
    license_key = f"LIC-{uuid.uuid4().hex[:12].upper()}"
    db_path = store_db_path_for_code(store_code)
    init_store_db(db_path)
    with get_master_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO stores (code, name, phone, address, db_path, active, device_limit, license_key, license_status, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'INACTIVE', ?)
            """,
            (store_code, name, phone, address, str(db_path), max(1, int(device_limit)), license_key, datetime_now()),
        )
        store_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    return row_to_dict(row) or {}


def update_store(
    store_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    device_limit: int | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if phone is not None:
        updates.append("phone = ?")
        params.append(phone)
    if address is not None:
        updates.append("address = ?")
        params.append(address)
    if device_limit is not None:
        updates.append("device_limit = ?")
        params.append(max(1, int(device_limit)))
    if not updates:
        return get_store_by_id(store_id)
    params.append(store_id)
    with get_master_connection() as conn:
        conn.execute(
            f"UPDATE stores SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    return row_to_dict(row)


def delete_store(store_id: int) -> dict[str, Any] | None:
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
        if row is None:
            return None
        db_path = row["db_path"]
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))

    try:
        path = Path(db_path)
        if path.exists():
            path.unlink()
    except Exception:
        pass

    return row_to_dict(row)


def update_store_license(
    store_id: int,
    *,
    status: str | None = None,
    activated_at: str | None = None,
    deactivated_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        updates.append("license_status = ?")
        params.append(status)
    if activated_at is not None:
        updates.append("license_activated_at = ?")
        params.append(activated_at)
    if deactivated_at is not None:
        updates.append("license_deactivated_at = ?")
        params.append(deactivated_at)
    if expires_at is not None:
        updates.append("license_expires_at = ?")
        params.append(expires_at)
    if not updates:
        return get_store_by_id(store_id)
    params.append(store_id)
    with get_master_connection() as conn:
        conn.execute(
            f"UPDATE stores SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    return row_to_dict(row)


def generate_store_code(name: str = "") -> str:
    base = "".join(ch for ch in name.lower().strip() if ch.isalnum())[:12]
    suffix = uuid.uuid4().hex[:4]
    if not base:
        base = "store"
    return f"{base}-{suffix}"


def _device_count(conn: sqlite3.Connection, store_id: int, *, active: int | None = None) -> int:
    query = "SELECT COUNT(*) AS count FROM devices WHERE store_id = ?"
    params: list[Any] = [store_id]
    if active is not None:
        query += " AND active = ?"
        params.append(active)
    row = conn.execute(query, tuple(params)).fetchone()
    return int((row or {"count": 0})["count"])


def _insert_device(
    conn: sqlite3.Connection,
    *,
    store_id: int,
    name: str,
    platform: str,
    device_key: str,
    device_fingerprint: str = "",
    active: int = 1,
    requested_at: str = "",
    approved_at: str = "",
    last_seen: str = "",
) -> dict[str, Any]:
    now = datetime_now()
    cursor = conn.execute(
        """
        INSERT INTO devices (
            store_id,
            name,
            platform,
            device_key,
            device_fingerprint,
            active,
            requested_at,
            approved_at,
            last_seen,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            store_id,
            name,
            platform,
            device_key,
            device_fingerprint,
            int(active),
            requested_at,
            approved_at,
            last_seen,
            now,
        ),
    )
    row = conn.execute("SELECT * FROM devices WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return row_to_dict(row) or {}


def create_device(store_id: int, name: str, platform: str = "desktop") -> dict[str, Any]:
    device_key = uuid.uuid4().hex
    now = datetime_now()
    with get_master_connection() as conn:
        store_row = conn.execute(
            "SELECT id, device_limit FROM stores WHERE id = ?",
            (store_id,),
        ).fetchone()
        if store_row is None:
            return {}
        current_count = _device_count(conn, store_id, active=1)
        device_limit = int(store_row["device_limit"] or 0)
        if current_count >= device_limit:
            raise ValueError("Device limit reached for this shop")
        row = _insert_device(
            conn,
            store_id=store_id,
            name=name,
            platform=platform,
            device_key=device_key,
            active=1,
            approved_at=now,
            last_seen=now,
        )
    return row


def request_device_activation(
    store_id: int,
    *,
    name: str,
    platform: str = "desktop",
    device_fingerprint: str,
) -> dict[str, Any]:
    fingerprint = device_fingerprint.strip()
    if not fingerprint:
        raise ValueError("Device fingerprint is required")

    now = datetime_now()
    with get_master_connection() as conn:
        store_row = conn.execute(
            "SELECT id, device_limit FROM stores WHERE id = ?",
            (store_id,),
        ).fetchone()
        if store_row is None:
            return {}

        existing = conn.execute(
            "SELECT * FROM devices WHERE store_id = ? AND device_fingerprint = ?",
            (store_id, fingerprint),
        ).fetchone()
        if existing is not None:
            conn.execute(
                """
                UPDATE devices
                SET name = ?, platform = ?, requested_at = COALESCE(NULLIF(requested_at, ''), ?)
                WHERE id = ?
                """,
                (name, platform, now, existing["id"]),
            )
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (existing["id"],)).fetchone()
            return row_to_dict(row) or {}

        current_active = _device_count(conn, store_id, active=1)
        device_limit = int(store_row["device_limit"] or 0)
        if current_active >= device_limit:
            raise ValueError("Device limit reached for this shop")

        row = _insert_device(
            conn,
            store_id=store_id,
            name=name,
            platform=platform,
            device_key=uuid.uuid4().hex,
            device_fingerprint=fingerprint,
            active=0,
            requested_at=now,
        )
    return row


def activate_device_by_key(device_key: str) -> dict[str, Any] | None:
    normalized = device_key.strip()
    if not normalized:
        return None
    now = datetime_now()
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_key = ?", (normalized,)).fetchone()
        if row is None:
            return None
        store_row = conn.execute("SELECT id, device_limit FROM stores WHERE id = ?", (row["store_id"],)).fetchone()
        if store_row is None:
            return None
        if int(row["active"] or 0) != 1:
            current_active = _device_count(conn, int(row["store_id"]), active=1)
            device_limit = int(store_row["device_limit"] or 0)
            if current_active >= device_limit:
                raise ValueError("Device limit reached for this shop")
            conn.execute(
                """
                UPDATE devices
                SET active = 1,
                    approved_at = COALESCE(NULLIF(approved_at, ''), ?),
                    last_seen = ?
                WHERE device_key = ?
                """,
                (now, now, normalized),
            )
        conn.execute("UPDATE devices SET last_seen = ? WHERE device_key = ?", (now, normalized))
        row = conn.execute("SELECT * FROM devices WHERE device_key = ?", (normalized,)).fetchone()
    return row_to_dict(row)


def list_devices(store_id: int) -> list[dict[str, Any]]:
    with get_master_connection() as conn:
        rows = conn.execute("SELECT * FROM devices WHERE store_id = ? ORDER BY id", (store_id,)).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def get_device_by_key(device_key: str) -> dict[str, Any] | None:
    with get_master_connection() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_key = ?", (device_key,)).fetchone()
    return row_to_dict(row)


def touch_device(device_key: str) -> None:
    with get_master_connection() as conn:
        conn.execute("UPDATE devices SET last_seen = ? WHERE device_key = ?", (datetime_now(), device_key))


def activate_store(code: str | None = None, store_id: int | None = None) -> dict[str, Any]:
    store: dict[str, Any] | None = None
    if store_id is not None:
        store = get_store_by_id(store_id)
    elif code:
        store = get_store_by_code(code)
    if store is None:
        store = ensure_default_store()
    db_path = Path(store["db_path"])
    init_store_db(db_path)
    set_active_store_db_path(db_path)
    set_active_store(store)
    return store


def datetime_now() -> str:
    return datetime.utcnow().isoformat()
