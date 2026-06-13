from fastapi import APIRouter

from services.backend_service import health_check, home, meta


router = APIRouter(tags=["meta"])

router.get("/")(home)
router.get("/health")(health_check)
router.get("/api/v1/meta")(meta)

