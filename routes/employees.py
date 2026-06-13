from fastapi import APIRouter

from services.backend_service import (
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    update_employee,
)


router = APIRouter(prefix="/api/v1/employees", tags=["employees"])

router.get("")(list_employees)
router.get("/{employee_id}")(get_employee)
router.post("")(create_employee)
router.put("/{employee_id}")(update_employee)
router.delete("/{employee_id}")(delete_employee)
