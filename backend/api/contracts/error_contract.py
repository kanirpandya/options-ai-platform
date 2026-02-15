"""
backend.api.contracts.error_contract

Purpose:
    Stable error contract for the API (codes + response model).
    Used by global exception handlers to ensure consistent client responses.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApiErrorCode(str, Enum):
    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"

    # Engine / analysis
    ENGINE_ERROR = "ENGINE_ERROR"
    ENGINE_TIMEOUT = "ENGINE_TIMEOUT"
    ENGINE_CONFIG_ERROR = "ENGINE_CONFIG_ERROR"


class ErrorResponse(BaseModel):
    request_id: str = Field(..., description="Request correlation id for debugging")
    error_code: ApiErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Optional structured details")
