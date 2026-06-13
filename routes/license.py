from fastapi import APIRouter

from services.backend_service import get_license, update_license


router = APIRouter(prefix="/api/v1/license", tags=["license"])

router.get("")(get_license)
router.put("")(update_license)

