from __future__ import annotations

from typing import List

from ..graph.state import (
    CoveredCallBias,
    FundamentalReport,
    FundamentalsView,
    GraphState,
    Stance,
)
from coveredcall_agents.fundamentals.mode import FundamentalsMode
from coveredcall_agents.fundamentals.mode_helpers import get_fundamentals_mode
from coveredcall_agents.trade_policy import decide_trade_action


def fundamental_node(state: GraphState) -> dict:
    snap = state.tools.get_fundamental_snapshot(state.ticker, state.as_of)
    updates = {"fundamentals_snapshot": snap}

    cfg = (state.config or {}) if getattr(state, "config", None) else {}
    mode = get_fundamentals_mode(cfg)

    fcfg = cfg.get("fundamentals", {}) or {}
    strong_growth = float(fcfg.get("strong_growth_pct", 5.0))
    strong_margin = float(fcfg.get("strong_oper_margin_pct", 10.0))
    min_margin = float(fcfg.get("min_oper_margin_pct", 5.0))
    max_d2e = float(fcfg.get("max_debt_to_equity", 2.0))

    points: List[str] = []
    risks: List[str] = []

    growth = snap.revenue_growth_yoy_pct
    opm = snap.operating_margin_pct
    d2e = snap.debt_to_equity

    bullish_signals = 0
    bearish_signals = 0

    if growth is not None:
        points.append(f"Revenue growth YoY: {growth:.1f}%")
        if growth >= strong_growth:
            bullish_signals += 1
        elif growth < 0:
            bearish_signals += 1
    else:
        risks.append("Missing revenue growth data")

    if opm is not None:
        points.append(f"Operating margin: {opm:.1f}%")
        if opm >= strong_margin:
            bullish_signals += 1
        elif opm < min_margin:
            bearish_signals += 1
    else:
        risks.append("Missing operating margin data")

    if d2e is not None:
        points.append(f"Debt-to-equity: {d2e:.2f}")
        if d2e > max_d2e:
            bearish_signals += 1
            risks.append("Leverage is elevated")
    else:
        risks.append("Missing leverage (debt-to-equity) data")

    # stance
    if bearish_signals >= 2:
        stance = Stance.BEARISH
    elif bullish_signals >= 2 and bearish_signals == 0:
        stance = Stance.BULLISH
    else:
        stance = Stance.NEUTRAL

    # bias
    if stance == Stance.BULLISH:
        bias = CoveredCallBias.UPSIDE
        points.append("Fundamentals tilt bullish → prefer higher strike / more OTM calls.")
    elif stance == Stance.BEARISH:
        bias = CoveredCallBias.CAUTION
        points.append("Fundamentals tilt bearish → consider no-trade or very conservative calls.")
    else:
        bias = CoveredCallBias.INCOME
        points.append("Fundamentals neutral → prefer income harvesting / closer strikes.")

    # confidence (guard quality)
    missing_fields = (snap.quality.missing_fields or []) if snap.quality else []
    warnings = (snap.quality.warnings or []) if snap.quality else []
    missing = len(missing_fields)
    confidence = 0.8 if missing == 0 else max(0.3, 0.7 - 0.1 * missing)

    # det_fundamentals baseline for BOTH modes
    updates["det_fundamentals"] = FundamentalsView(
        stance=stance,
        covered_call_bias=bias,
        confidence=confidence,
        key_points=points[:4],
        risks=(risks + warnings)[:2],
    )

    # LLM/Agentic modes: snapshot + det baseline only
    if mode in (FundamentalsMode.LLM, FundamentalsMode.AGENTIC):
        return updates

    # Deterministic mode: build full report too
    report = FundamentalReport(
        ticker=snap.ticker,
        stance=stance,
        covered_call_bias=bias,
        confidence=confidence,
        key_points=points,
        risks=risks + warnings,
        snapshot=snap,
    )

    # Phase 2: always populate action/action_reason on the report (enum-based)
    if getattr(report, "action", None) is None or getattr(report, "action_reason", None) is None:
        decision = decide_trade_action(
            stance=report.stance,
            bias=report.covered_call_bias,
            confidence=report.confidence,
        )
        report = report.model_copy(update={"action": decision.action, "action_reason": decision.reason})

    updates["fundamentals_report"] = report
    return updates
