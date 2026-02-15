"""
backend.api.errors

Purpose:
    Internal exception types for API error handling.
    Routes raise ApiError; global handler converts to ErrorResponse.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.api.contracts.error_contract import ApiErrorCode


@dataclass(frozen=True)
class ApiError(Exception):
    status_code: int
    error_code: ApiErrorCode
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"
