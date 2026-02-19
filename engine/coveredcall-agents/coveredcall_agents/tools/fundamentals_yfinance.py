"""
coveredcall_agents.tools.fundamentals_yfinance

Purpose:
    Fetch a fundamentals snapshot using yfinance (Yahoo Finance) and return a
    FundamentalSnapshot with quality/missing_fields/warnings.

Notes:
    - Sets snapshot.as_of to the request timestamp (same as quality.as_of).
    - Sets snapshot.source to "yfinance".
    - Sets snapshot.metadata with basic provider context.

Author:
    Kanir Pandya

Created:
    2026-02-18
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import yfinance as yf

from ..graph.state import DataQuality, FundamentalSnapshot


def _get_num(d: Dict[str, Any], key: str) -> Optional[float]:
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def get_fundamental_snapshot_yfinance(
    ticker: str,
    as_of: datetime | None = None,
) -> FundamentalSnapshot:
    """
    Tool: fetch a fundamentals snapshot using yfinance (Yahoo Finance).

    Returns:
        FundamentalSnapshot with missing_fields/warnings populated when data is absent.
    """
    as_of = as_of or datetime.now(timezone.utc)
    t = ticker.upper().strip()

    missing: list[str] = []
    warnings: list[str] = []

    try:
        yt = yf.Ticker(t)
        info = yt.info or {}
    except Exception as e:
        return FundamentalSnapshot(
            ticker=t,
            as_of=as_of,
            source="yfinance",
            metadata={"provider": "yfinance", "ticker": t},
            quality=DataQuality(
                as_of=as_of,
                is_stub=False,
                missing_fields=["ALL"],
                warnings=[f"yfinance error: {type(e).__name__}: {e}"],
            ),
        )

    price = _get_num(info, "currentPrice") or _get_num(info, "regularMarketPrice")
    market_cap = _get_num(info, "marketCap")
    if price is None:
        missing.append("price")
    if market_cap is None:
        missing.append("market_cap")

    # Growth (often decimals like 0.12 -> 12%)
    rev_growth = _get_num(info, "revenueGrowth")
    revenue_growth_yoy_pct = rev_growth * 100.0 if rev_growth is not None else None
    if revenue_growth_yoy_pct is None:
        missing.append("revenue_growth_yoy_pct")

    eps_growth = _get_num(info, "earningsGrowth")
    eps_growth_yoy_pct = eps_growth * 100.0 if eps_growth is not None else None
    if eps_growth_yoy_pct is None:
        missing.append("eps_growth_yoy_pct")

    # Margins (often decimals like 0.30 -> 30%)
    gm = _get_num(info, "grossMargins")
    gross_margin_pct = gm * 100.0 if gm is not None else None
    if gross_margin_pct is None:
        missing.append("gross_margin_pct")

    om = _get_num(info, "operatingMargins")
    operating_margin_pct = om * 100.0 if om is not None else None
    if operating_margin_pct is None:
        missing.append("operating_margin_pct")

    # debtToEquity sometimes reported like 150.0 (meaning 150%), convert to 1.5
    d2e_raw = _get_num(info, "debtToEquity")
    if d2e_raw is None:
        debt_to_equity = None
        missing.append("debt_to_equity")
    else:
        debt_to_equity = d2e_raw / 100.0 if d2e_raw > 10 else d2e_raw

    if not info:
        warnings.append("yfinance returned empty info dict")

    return FundamentalSnapshot(
        ticker=t,
        as_of=as_of,
        source="yfinance",
        metadata={
            "provider": "yfinance",
            "ticker": t,
            # Keep metadata small/stable; avoid dumping full info dict.
        },
        price=price,
        market_cap=market_cap,
        revenue_growth_yoy_pct=revenue_growth_yoy_pct,
        eps_growth_yoy_pct=eps_growth_yoy_pct,
        gross_margin_pct=gross_margin_pct,
        operating_margin_pct=operating_margin_pct,
        debt_to_equity=debt_to_equity,
        quality=DataQuality(
            as_of=as_of,
            is_stub=False,
            missing_fields=missing,
            warnings=warnings,
        ),
    )
