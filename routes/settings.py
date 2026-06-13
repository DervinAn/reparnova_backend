from fastapi import APIRouter

from services.backend_service import get_settings, update_settings


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

router.get("")(get_settings)
router.put("")(update_settings)

