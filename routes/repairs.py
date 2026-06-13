from fastapi import APIRouter

from services.backend_service import (
    create_repair,
    delete_repair,
    get_repair,
    list_repairs,
    update_repair,
    update_repair_status,
)


router = APIRouter(prefix="/api/v1/repairs", tags=["repairs"])

router.get("")(list_repairs)
router.post("")(create_repair)
router.put("/{repair_id}")(update_repair)
router.get("/{repair_id}")(get_repair)
router.post("/{repair_id}/status")(update_repair_status)
router.delete("/{repair_id}")(delete_repair)

