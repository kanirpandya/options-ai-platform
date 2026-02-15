from fastapi import APIRouter
from backend.api.routes.v1.analysis import router as analysis_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(analysis_router)
