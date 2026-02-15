"""
backend.api.routes.v1.health

Purpose:
    Versioned health endpoint for API clients.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
