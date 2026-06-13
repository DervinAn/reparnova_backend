from fastapi import APIRouter

from services.backend_service import (
    create_spare_part,
    delete_spare_part,
    get_spare_part,
    list_spare_parts,
    update_spare_part,
)


router = APIRouter(prefix="/api/v1/spare-parts", tags=["spare-parts"])

router.get("")(list_spare_parts)
router.get("/{part_id}")(get_spare_part)
router.post("")(create_spare_part)
router.put("/{part_id}")(update_spare_part)
router.delete("/{part_id}")(delete_spare_part)
