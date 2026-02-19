"""
coveredcall_agents.tools.fundamentals

Purpose:
    Provide a deterministic stub fundamentals snapshot for Phase 1 / offline runs.

Notes:
    - Sets snapshot.as_of to the request timestamp (same as quality.as_of).
    - Sets snapshot.source to "stub".
    - Sets snapshot.metadata with basic provider context.

Author:
    Kanir Pandya

Created:
    2026-02-18
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..graph.state import DataQuality, FundamentalSnapshot


def get_fundamental_snapshot(
    ticker: str,
    as_of: datetime | None = None,
) -> FundamentalSnapshot:
    """
    Tool: fetch fundamental snapshot for a ticker.

    Stub implementation for Phase 1.
    Replace later with yfinance / SEC / other providers.
    """
    as_of = as_of or datetime.now(timezone.utc)
    t = ticker.upper().strip()

    base_meta = {"provider": "stub", "ticker": t}

    # ---- STUB DATA (safe + deterministic) ----
    if t == "AAPL":
        return FundamentalSnapshot(
            ticker="AAPL",
            as_of=as_of,
            source="stub",
            metadata=base_meta,
            price=190.0,
            market_cap=2.9e12,
            revenue_growth_yoy_pct=2.0,
            eps_growth_yoy_pct=6.0,
            gross_margin_pct=44.0,
            operating_margin_pct=30.0,
            debt_to_equity=1.5,
            quality=DataQuality(
                as_of=as_of,
                is_stub=True,
            ),
        )

    if t == "MSFT":
        return FundamentalSnapshot(
            ticker="MSFT",
            as_of=as_of,
            source="stub",
            metadata=base_meta,
            price=420.0,
            market_cap=3.1e12,
            revenue_growth_yoy_pct=12.0,
            eps_growth_yoy_pct=18.0,
            gross_margin_pct=69.0,
            operating_margin_pct=42.0,
            debt_to_equity=0.6,
            quality=DataQuality(
                as_of=as_of,
                is_stub=True,
            ),
        )

    if t == "TSLA":
        return FundamentalSnapshot(
            ticker="TSLA",
            as_of=as_of,
            source="stub",
            metadata=base_meta,
            price=250.0,
            market_cap=8.0e11,
            revenue_growth_yoy_pct=5.0,
            eps_growth_yoy_pct=-10.0,
            gross_margin_pct=18.0,
            operating_margin_pct=8.0,
            debt_to_equity=0.2,
            quality=DataQuality(
                as_of=as_of,
                is_stub=True,
                warnings=["EPS growth negative in stub snapshot"],
            ),
        )

    # ---- FALLBACK (unknown ticker) ----
    return FundamentalSnapshot(
        ticker=t,
        as_of=as_of,
        source="stub",
        metadata=base_meta,
        quality=DataQuality(
            as_of=as_of,
            is_stub=True,
            missing_fields=[
                "price",
                "market_cap",
                "revenue_growth_yoy_pct",
                "operating_margin_pct",
                "debt_to_equity",
            ],
            warnings=["No stub fundamentals available for this ticker"],
        ),
    )
