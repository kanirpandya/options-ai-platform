"""
backend.api.routes.health

Purpose:
    Health endpoints for container/orchestrator checks.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.contracts.api_paths import ApiPaths
from backend.api.contracts.api_tags import ApiTags

_paths = ApiPaths()
_tags = ApiTags()

router = APIRouter(tags=[_tags.health])


@router.get(_paths.health)
def health() -> dict:
    return {"ok": True}
