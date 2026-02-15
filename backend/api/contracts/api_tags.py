"""
backend.api.contracts.api_tags

Purpose:
    Central definition of FastAPI tags to avoid scattered string literals.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiTags:
    health: str = "health"
    analysis: str = "analysis"
