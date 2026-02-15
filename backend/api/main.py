"""
backend.api.main

Purpose:
    FastAPI application entrypoint for the Options AI Platform backend API.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.settings import get_settings
from backend.api.routes.health import router as health_router
from backend.api.routes.analysis import router as analysis_router

from backend.api.middleware.request_id import RequestIdMiddleware
from backend.api.contracts.request_id_policy import RequestIdPolicy
from backend.api.logging.logging_config import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging()

    app = FastAPI(title=settings.service_name, version=settings.service_version)

    app.add_middleware(RequestIdMiddleware, policy=RequestIdPolicy())

    app.include_router(health_router)
    app.include_router(analysis_router)

    return app

app = create_app()
