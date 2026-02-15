from fastapi import APIRouter

from backend.api.routes.v1.analysis import router as analysis_router
from backend.api.routes.v1.health import router as health_router
from backend.api.routes.v1.info import router as info_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health_router)
v1_router.include_router(info_router)
v1_router.include_router(analysis_router)
