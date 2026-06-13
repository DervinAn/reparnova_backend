from fastapi import APIRouter

from services.backend_service import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

router.get("")(list_categories)
router.post("")(create_category)
router.put("/{category_id}")(update_category)
router.get("/{category_id}")(get_category)
router.delete("/{category_id}")(delete_category)

