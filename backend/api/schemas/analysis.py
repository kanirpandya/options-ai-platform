"""
backend.api.schemas.analysis

Purpose:
    Request/response schemas for the /v1/analyze API endpoint.
    Keeps the FastAPI contract synchronized with route override logic.

Notes:
    - Optional fields allow API callers to override engine configuration safely.
    - Validation happens at the API boundary (Pydantic), before engine execution.
    - extra="forbid" prevents silent client typos (e.g., "providre").
    - provider/mode are enums to prevent invalid values.

Author:
    Kanir Pandya

Updated:
    2026-02-15
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FundamentalsProvider(str, Enum):
    """
    Supported fundamentals providers (API-level).
    Keep in sync with engine providers you actually support.
    """
    yahoo = "yahoo"
    yahoo_stub = "yahoo_stub"


class FundamentalsMode(str, Enum):
    """
    Supported fundamentals modes (API-level).
    Keep in sync with engine modes you actually support.
    """
    deterministic = "deterministic"
    llm = "llm"
    agentic = "agentic"
    det = "det"  # allow legacy shorthand if your engine accepts it


class AnalyzeRequest(BaseModel):
    """
    Request payload for /v1/analyze.

    Only `ticker` is required. Optional fields are overrides applied onto
    the base engine config by _apply_overrides().
    """

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(
        ...,
        description="Ticker symbol (letters/digits with optional '.' or '-' ; 1–12 chars).",
        examples=["AAPL", "BRK.B", "RDS-A"],
    )

    # ---- Optional overrides (used by backend/api/routes/analysis.py:_apply_overrides) ----
    provider: Optional[FundamentalsProvider] = Field(
        default=None,
        description="Fundamentals provider override.",
        examples=["yahoo_stub"],
    )

    mode: Optional[FundamentalsMode] = Field(
        default=None,
        description="Fundamentals execution mode override.",
        examples=["deterministic"],
    )

    force_debate: Optional[bool] = Field(
        default=None,
        description="If true, forces debate workflow (when supported).",
        examples=[False],
    )

    output: Optional[Literal["pretty", "json"]] = Field(
        default=None,
        description="Output format override (if API supports it).",
        examples=["json"],
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,11}", v):
            raise ValueError(
                "Invalid ticker format. Use letters/digits and optional '.' or '-' (1–12 chars)."
            )
        return v
