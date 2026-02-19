# backend/api/models.py
"""
backend.api.models

Purpose:
    Request/response contracts for the FastAPI wrapper.
    The response contract is intentionally "public" and stable.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from typing import Any, Literal
import re
from pydantic import field_validator

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        t = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", t):
            raise ValueError("Invalid ticker format. Use letters/digits and optional '.' or '-' (1–12 chars).")
        return t


class SnapshotQuality(BaseModel):
    as_of: str
    is_stub: bool
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FundamentalsSnapshot(BaseModel):
    ticker: str
    price: float | None = None
    market_cap: float | None = None
    revenue_growth_yoy_pct: float | None = None
    eps_growth_yoy_pct: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    debt_to_equity: float | None = None
    quality: SnapshotQuality | None = None


class FinalFundamentals(BaseModel):
    stance: str
    covered_call_bias: str
    confidence: float
    source: Literal["det", "deterministic", "llm", "agentic", "unknown"] | str
    rationale: str | None = None


class FundamentalsReport(BaseModel):
    ticker: str
    stance: str
    covered_call_bias: str
    confidence: float
    key_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    appendix: Any | None = None
    explain: Any | None = None

    action: str | None = None
    action_reason: str | None = None


class AnalyzeResponseV1(BaseModel):
    ticker: str
    as_of: str

    fundamentals_snapshot: FundamentalsSnapshot | None = None
    fundamentals_report: FundamentalsReport | None = None
    final_fundamentals: FinalFundamentals | None = None
