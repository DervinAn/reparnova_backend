from fastapi import APIRouter

from services.backend_service import (
    create_product,
    delete_product,
    delete_storage_placement,
    duplicate_product,
    get_product,
    list_products,
    list_storage_placements,
    save_storage_placement,
    update_product,
)


router = APIRouter(prefix="/api/v1/products", tags=["products"])
storage_router = APIRouter(prefix="/api/v1/storage-placements", tags=["products"])

router.get("")(list_products)
router.get("/{product_id}")(get_product)
router.post("")(create_product)
router.put("/{product_id}")(update_product)
router.delete("/{product_id}")(delete_product)
router.post("/{product_id}/duplicate")(duplicate_product)

storage_router.get("")(list_storage_placements)
storage_router.post("")(save_storage_placement)
storage_router.delete("/{placement_id}")(delete_storage_placement)

