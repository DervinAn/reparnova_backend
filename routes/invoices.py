from fastapi import APIRouter

from services.backend_service import (
    cancel_invoice,
    create_invoice,
    get_invoice,
    list_invoices,
    update_invoice,
)


router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])

router.get("")(list_invoices)
router.post("")(create_invoice)
router.put("/{invoice_number}")(update_invoice)
router.get("/{invoice_number}")(get_invoice)
router.post("/{invoice_number}/cancel")(cancel_invoice)

