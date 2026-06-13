from fastapi import APIRouter

from services.backend_service import (
    create_expense,
    delete_expense,
    export_expenses_csv,
    get_expense,
    list_expenses,
    update_expense,
)


router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

router.get("")(list_expenses)
router.post("")(create_expense)
router.put("/{expense_id}")(update_expense)
router.get("/{expense_id}")(get_expense)
router.delete("/{expense_id}")(delete_expense)
router.get("/export.csv")(export_expenses_csv)

