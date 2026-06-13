from fastapi import APIRouter

from services.backend_service import analytics


router = APIRouter(prefix="/api/v1", tags=["analytics"])

router.get("/analytics")(analytics)

