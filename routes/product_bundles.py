from fastapi import APIRouter

from services.backend_service import (
    create_product_bundle,
    delete_product_bundle,
    get_product_bundle,
    list_product_bundles,
    update_product_bundle,
)


router = APIRouter(prefix="/api/v1/product-bundles", tags=["product-bundles"])

router.get("")(list_product_bundles)
router.get("/{bundle_id}")(get_product_bundle)
router.post("")(create_product_bundle)
router.put("/{bundle_id}")(update_product_bundle)
router.delete("/{bundle_id}")(delete_product_bundle)
