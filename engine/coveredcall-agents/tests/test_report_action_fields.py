"""
tests/test_report_action_fields.py

Purpose:
    Ensure FundamentalReport includes trade-policy action fields and serializes them.
    We construct a minimal snapshot/quality object using model_construct() so this test
    doesn't depend on every required snapshot field.
"""

from __future__ import annotations

from typing import Any, Type

from coveredcall_agents.contracts.enums import CoveredCallBias, Stance, TradeAction
import coveredcall_agents.graph.state as gs
from coveredcall_agents.graph.state import FundamentalReport


def _get_class(name_candidates: list[str]) -> Type[Any]:
    for n in name_candidates:
        cls = getattr(gs, n, None)
        if cls is not None:
            return cls
    raise RuntimeError(f"Could not find any of these classes in graph.state: {name_candidates}")


def _make_min_snapshot(ticker: str) -> Any:
    # Try common class names first; fallback keeps this test resilient to refactors.
    SnapshotCls = _get_class(["FundamentalsSnapshot", "FundamentalSnapshot", "Snapshot"])
    QualityCls = getattr(gs, "SnapshotQuality", None) or getattr(gs, "DataQuality", None) or getattr(gs, "Quality", None)

    # Construct a minimal quality object if a class exists; otherwise allow None.
    quality_obj = QualityCls.model_construct() if QualityCls is not None else None

    # Construct a minimal snapshot object. We set ticker/quality because your validation complained about them,
    # but we intentionally avoid filling every required snapshot field for this test.
    return SnapshotCls.model_construct(ticker=ticker, quality=quality_obj)


def test_fundamental_report_includes_action_fields() -> None:
    snap = _make_min_snapshot("AAPL")

    r = FundamentalReport(
        ticker="AAPL",
        stance=Stance.NEUTRAL,
        covered_call_bias=CoveredCallBias.INCOME,
        confidence=0.7,
        key_points=[],
        snapshot=snap,
        action=TradeAction.SELL_CALL,
        action_reason="test",
    )

    d = r.model_dump()

    # Be explicit that fields exist + round-trip
    assert "action" in d
    assert "action_reason" in d
    assert d["action"] == TradeAction.SELL_CALL
    assert d["action_reason"] == "test"
