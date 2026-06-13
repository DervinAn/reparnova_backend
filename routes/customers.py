from fastapi import APIRouter

from services.backend_service import (
    create_customer,
    delete_customer,
    get_customer,
    list_customers,
    update_customer,
)


router = APIRouter(prefix="/api/v1/customers", tags=["customers"])

router.get("")(list_customers)
router.post("")(create_customer)
router.put("/{customer_id}")(update_customer)
router.get("/{customer_id}")(get_customer)
router.delete("/{customer_id}")(delete_customer)

