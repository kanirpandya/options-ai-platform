"""
coveredcall_agents/agents/debate_agents.py

Purpose:
    Implements LLM-driven bull, bear, debate, and proposal nodes used in
    the fundamentals analysis pipeline.

Phase 2 change:
    Skip bull/bear/debate unless debate is explicitly requested (force_debate)
    or divergence severity indicates we should debate (MAJOR/CRITICAL/EXTREME).
"""

from __future__ import annotations

from typing import Any

from coveredcall_agents.trade_policy import decide_trade_action
from coveredcall_agents.utils.divergence import format_divergence_report
from coveredcall_agents.utils.logging import LogCtx, get_logger, with_ctx

from ..graph.state import (
    AgentArgument,
    CoveredCallBias,
    DebateSummary,
    FundamentalReport,
    GraphState,
    Stance,
)
from ..llm.debate_prompts import (
    BEAR_SYSTEM,
    BULL_SYSTEM,
    DEBATE_SYSTEM,
    bear_user,
    bull_user,
    debate_user,
)

logger = get_logger(__name__)


# ---------- formatting helpers ----------


def _format_debate_block(state: GraphState) -> str:
    ds = getattr(state, "debate_summary", None)
    if ds is None:
        return ""

    d = ds.model_dump() if hasattr(ds, "model_dump") else dict(ds)
    lines: list[str] = ["LLM Debate Summary", "-----------------"]

    syn = list(d.get("synthesis") or [])
    dis = list(d.get("disagreements") or [])
    summary = (d.get("summary") or "").strip() if isinstance(d.get("summary"), str) else ""
    key_points = list(d.get("key_points") or [])

    wrote_any = False

    if summary:
        lines.append(f"Summary: {summary}")
        wrote_any = True

    if syn:
        lines += ["", "Synthesis", "---------"]
        for i, s in enumerate(syn[:2], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    if dis:
        lines += ["", "Disagreements", "-------------"]
        for i, s in enumerate(dis[:2], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    if key_points:
        lines += ["", "Key points", "----------"]
        for i, s in enumerate(key_points[:4], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    return "\n".join(lines).rstrip() if wrote_any else ""


def _format_agentic_block(state: GraphState) -> str:
    af = getattr(state, "agentic_fundamentals", None)
    ar = getattr(state, "agentic_result", None)
    if af is None and ar is None:
        return ""

    lines: list[str] = ["Agentic Fundamentals", "-------------------"]

    summary = str(getattr(ar, "summary", "") or "").strip() if ar is not None else ""
    if summary:
        lines.append(f"Summary: {summary}")

    stance = getattr(af, "stance", None) if af else getattr(ar, "stance", None)
    bias = getattr(af, "covered_call_bias", None) if af else getattr(ar, "covered_call_bias", None)
    conf = getattr(af, "confidence", None) if af else getattr(ar, "confidence", None)

    stance_s = getattr(stance, "value", None) or (str(stance) if stance else "—")
    bias_s = getattr(bias, "value", None) or (str(bias) if bias else "—")
    try:
        conf_str = f"{float(conf):.2f}" if conf is not None else "—"
    except Exception:
        conf_str = "—"

    lines.append(f"Stance: {stance_s} | Bias: {bias_s} | Confidence: {conf_str}")
    lines.append("")

    bullets = list(getattr(af, "key_points", []) or []) if af else []
    risks = list(getattr(af, "risks", []) or []) if af else []
    if not bullets and ar:
        bullets = list(getattr(ar, "bullets", []) or [])
    if not risks and ar:
        risks = list(getattr(ar, "risks", []) or [])

    if bullets:
        lines += ["Bullets", "-------"]
        for i, b in enumerate(bullets[:4], 1):
            if b := str(b).strip():
                lines.append(f"{i}. {b}")
        lines.append("")

    if risks:
        lines += ["Risks", "-----"]
        for r in risks[:4]:
            if r := str(r).strip():
                lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _join_appendix(*parts: str) -> str:
    blocks = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(blocks) if blocks else ""


# ---------- debate gating (Phase 2) ----------


def _debate_enabled(state: GraphState) -> bool:
    """
    Debate is expensive (3 extra LLM calls). Only run bull/bear/debate if:
      - force_debate is enabled (CLI flag), OR
      - divergence severity suggests misalignment (MAJOR/CRITICAL/EXTREME)
    """
    fcfg = (state.config.get("fundamentals", {}) or {})
    if bool(fcfg.get("force_debate")):
        return True

    dr = getattr(state, "divergence_report", None)
    sev = getattr(dr, "severity", None) if dr is not None else None
    sev_v = getattr(sev, "value", None) or (str(sev) if sev is not None else "")
    return sev_v in {"MAJOR", "CRITICAL", "EXTREME"}


# ---------- bull / bear / debate ----------


def bull_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("bull_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("bull_node: state.llm is None (mode=llm required)")

    lgr = with_ctx(logger, LogCtx(node="bull_node", ticker=state.ticker))

    try:
        bull = state.llm.generate_json(
            system=BULL_SYSTEM,
            user=bull_user(state.fundamentals_snapshot, state.config),
            schema=AgentArgument.model_json_schema(),
            model=AgentArgument,
        )
        return {"bull_case": bull}
    except Exception as e:
        lgr.warning("LLM failed; using fallback (%s)", type(e).__name__)
        return {
            "bull_case": AgentArgument(
                stance=Stance.NEUTRAL,
                covered_call_bias=CoveredCallBias.INCOME,
                confidence=0.30,
                bullets=["Bull case unavailable (LLM timeout); continuing without it."],
                risks=["Debate may be incomplete due to bull-side timeout."],
            )
        }


def bear_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("bear_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("bear_node: state.llm is None (mode=llm required)")

    lgr = with_ctx(logger, LogCtx(node="bear_node", ticker=state.ticker))

    try:
        bear = state.llm.generate_json(
            system=BEAR_SYSTEM,
            user=bear_user(state.fundamentals_snapshot, state.config),
            schema=AgentArgument.model_json_schema(),
            model=AgentArgument,
        )
        return {"bear_case": bear}
    except Exception as e:
        lgr.warning("LLM failed; using fallback (%s)", type(e).__name__)
        return {
            "bear_case": AgentArgument(
                stance=Stance.NEUTRAL,
                covered_call_bias=CoveredCallBias.CAUTION,
                confidence=0.30,
                bullets=["Bear case unavailable (LLM timeout); continuing without it."],
                risks=["Debate may be incomplete due to bear-side timeout."],
            )
        }


def debate_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    lgr = with_ctx(logger, LogCtx(node="debate_node", ticker=state.ticker))

    lgr.debug(
        "entered existing_summary=%s bull=%s bear=%s",
        state.debate_summary is not None,
        state.bull_case is not None,
        state.bear_case is not None,
    )

    if state.debate_summary is not None:
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("debate_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("debate_node: state.llm is None (mode=llm required)")

    if state.bull_case is None or state.bear_case is None:
        return {
            "debate_summary": DebateSummary(
                bull=state.bull_case
                or AgentArgument(
                    stance=Stance.NEUTRAL,
                    covered_call_bias=CoveredCallBias.INCOME,
                    confidence=0.30,
                    bullets=[],
                    risks=[],
                ),
                bear=state.bear_case
                or AgentArgument(
                    stance=Stance.NEUTRAL,
                    covered_call_bias=CoveredCallBias.INCOME,
                    confidence=0.30,
                    bullets=[],
                    risks=[],
                ),
                synthesis=["Debate skipped: missing bull_case and/or bear_case."],
                disagreements=[],
            )
        }

    try:
        debate = state.llm.generate_json(
            system=DEBATE_SYSTEM,
            user=debate_user(
                snapshot=state.fundamentals_snapshot,
                bull=state.bull_case.model_dump(),
                bear=state.bear_case.model_dump(),
            ),
            schema=DebateSummary.model_json_schema(),
            model=DebateSummary,
        )
        return {"debate_summary": debate}
    except Exception as e:
        lgr.warning("Debate failed; using fallback (%s)", type(e).__name__)
        return {
            "debate_summary": DebateSummary(
                bull=state.bull_case,
                bear=state.bear_case,
                synthesis=[f"Debate JSON parse failed; fallback used ({type(e).__name__})."],
                disagreements=[],
            )
        }


# ---------- final report patching ----------


"""
coveredcall_agents/agents/debate_agents.py

Purpose:
    Implements LLM-driven bull, bear, debate, and proposal nodes used in
    the fundamentals analysis pipeline.

Phase 2 change:
    Skip bull/bear/debate unless debate is explicitly requested (force_debate)
    or divergence severity indicates we should debate (MAJOR/CRITICAL/EXTREME).
"""

from typing import Any

from coveredcall_agents.trade_policy import decide_trade_action
from coveredcall_agents.utils.divergence import format_divergence_report
from coveredcall_agents.utils.logging import LogCtx, get_logger, with_ctx

from ..graph.state import (
    AgentArgument,
    CoveredCallBias,
    DebateSummary,
    FundamentalReport,
    GraphState,
    Stance,
)
from ..llm.debate_prompts import (
    BEAR_SYSTEM,
    BULL_SYSTEM,
    DEBATE_SYSTEM,
    bear_user,
    bull_user,
    debate_user,
)

logger = get_logger(__name__)


# ---------- formatting helpers ----------


def _format_debate_block(state: GraphState) -> str:
    ds = getattr(state, "debate_summary", None)
    if ds is None:
        return ""

    d = ds.model_dump() if hasattr(ds, "model_dump") else dict(ds)
    lines: list[str] = ["LLM Debate Summary", "-----------------"]

    syn = list(d.get("synthesis") or [])
    dis = list(d.get("disagreements") or [])
    summary = (d.get("summary") or "").strip() if isinstance(d.get("summary"), str) else ""
    key_points = list(d.get("key_points") or [])

    wrote_any = False

    if summary:
        lines.append(f"Summary: {summary}")
        wrote_any = True

    if syn:
        lines += ["", "Synthesis", "---------"]
        for i, s in enumerate(syn[:2], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    if dis:
        lines += ["", "Disagreements", "-------------"]
        for i, s in enumerate(dis[:2], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    if key_points:
        lines += ["", "Key points", "----------"]
        for i, s in enumerate(key_points[:4], 1):
            if s := str(s).strip():
                lines.append(f"{i}. {s}")
                wrote_any = True

    return "\n".join(lines).rstrip() if wrote_any else ""


def _format_agentic_block(state: GraphState) -> str:
    af = getattr(state, "agentic_fundamentals", None)
    ar = getattr(state, "agentic_result", None)
    if af is None and ar is None:
        return ""

    lines: list[str] = ["Agentic Fundamentals", "-------------------"]

    summary = str(getattr(ar, "summary", "") or "").strip() if ar is not None else ""
    if summary:
        lines.append(f"Summary: {summary}")

    stance = getattr(af, "stance", None) if af else getattr(ar, "stance", None)
    bias = getattr(af, "covered_call_bias", None) if af else getattr(ar, "covered_call_bias", None)
    conf = getattr(af, "confidence", None) if af else getattr(ar, "confidence", None)

    stance_s = getattr(stance, "value", None) or (str(stance) if stance else "—")
    bias_s = getattr(bias, "value", None) or (str(bias) if bias else "—")
    try:
        conf_str = f"{float(conf):.2f}" if conf is not None else "—"
    except Exception:
        conf_str = "—"

    lines.append(f"Stance: {stance_s} | Bias: {bias_s} | Confidence: {conf_str}")
    lines.append("")

    bullets = list(getattr(af, "key_points", []) or []) if af else []
    risks = list(getattr(af, "risks", []) or []) if af else []
    if not bullets and ar:
        bullets = list(getattr(ar, "bullets", []) or [])
    if not risks and ar:
        risks = list(getattr(ar, "risks", []) or [])

    if bullets:
        lines += ["Bullets", "-------"]
        for i, b in enumerate(bullets[:4], 1):
            if b := str(b).strip():
                lines.append(f"{i}. {b}")
        lines.append("")

    if risks:
        lines += ["Risks", "-----"]
        for r in risks[:4]:
            if r := str(r).strip():
                lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _join_appendix(*parts: str) -> str:
    blocks = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(blocks) if blocks else ""


# ---------- debate gating (Phase 2) ----------


def _debate_enabled(state: GraphState) -> bool:
    """
    Debate is expensive (3 extra LLM calls). Only run bull/bear/debate if:
      - force_debate is enabled (CLI flag), OR
      - divergence severity suggests misalignment (MAJOR/CRITICAL/EXTREME)
    """
    fcfg = (state.config.get("fundamentals", {}) or {})
    if bool(fcfg.get("force_debate")):
        return True

    dr = getattr(state, "divergence_report", None)
    sev = getattr(dr, "severity", None) if dr is not None else None
    sev_v = getattr(sev, "value", None) or (str(sev) if sev is not None else "")
    return sev_v in {"MAJOR", "CRITICAL", "EXTREME"}


# ---------- bull / bear / debate ----------


def bull_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("bull_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("bull_node: state.llm is None (mode=llm required)")

    lgr = with_ctx(logger, LogCtx(node="bull_node", ticker=state.ticker))

    try:
        bull = state.llm.generate_json(
            system=BULL_SYSTEM,
            user=bull_user(state.fundamentals_snapshot, state.config),
            schema=AgentArgument.model_json_schema(),
            model=AgentArgument,
        )
        return {"bull_case": bull}
    except Exception as e:
        lgr.warning("LLM failed; using fallback (%s)", type(e).__name__)
        return {
            "bull_case": AgentArgument(
                stance=Stance.NEUTRAL,
                covered_call_bias=CoveredCallBias.INCOME,
                confidence=0.30,
                bullets=["Bull case unavailable (LLM timeout); continuing without it."],
                risks=["Debate may be incomplete due to bull-side timeout."],
            )
        }


def bear_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("bear_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("bear_node: state.llm is None (mode=llm required)")

    lgr = with_ctx(logger, LogCtx(node="bear_node", ticker=state.ticker))

    try:
        bear = state.llm.generate_json(
            system=BEAR_SYSTEM,
            user=bear_user(state.fundamentals_snapshot, state.config),
            schema=AgentArgument.model_json_schema(),
            model=AgentArgument,
        )
        return {"bear_case": bear}
    except Exception as e:
        lgr.warning("LLM failed; using fallback (%s)", type(e).__name__)
        return {
            "bear_case": AgentArgument(
                stance=Stance.NEUTRAL,
                covered_call_bias=CoveredCallBias.CAUTION,
                confidence=0.30,
                bullets=["Bear case unavailable (LLM timeout); continuing without it."],
                risks=["Debate may be incomplete due to bear-side timeout."],
            )
        }


def debate_node(state: GraphState) -> dict:
    # Phase 2: skip unless debate is enabled
    if not _debate_enabled(state):
        return {}

    lgr = with_ctx(logger, LogCtx(node="debate_node", ticker=state.ticker))

    lgr.debug(
        "entered existing_summary=%s bull=%s bear=%s",
        state.debate_summary is not None,
        state.bull_case is not None,
        state.bear_case is not None,
    )

    if state.debate_summary is not None:
        return {}

    if state.fundamentals_snapshot is None:
        raise RuntimeError("debate_node: fundamentals_snapshot missing")
    if state.llm is None:
        raise RuntimeError("debate_node: state.llm is None (mode=llm required)")

    if state.bull_case is None or state.bear_case is None:
        return {
            "debate_summary": DebateSummary(
                bull=state.bull_case
                or AgentArgument(
                    stance=Stance.NEUTRAL,
                    covered_call_bias=CoveredCallBias.INCOME,
                    confidence=0.30,
                    bullets=[],
                    risks=[],
                ),
                bear=state.bear_case
                or AgentArgument(
                    stance=Stance.NEUTRAL,
                    covered_call_bias=CoveredCallBias.INCOME,
                    confidence=0.30,
                    bullets=[],
                    risks=[],
                ),
                synthesis=["Debate skipped: missing bull_case and/or bear_case."],
                disagreements=[],
            )
        }

    try:
        debate = state.llm.generate_json(
            system=DEBATE_SYSTEM,
            user=debate_user(
                snapshot=state.fundamentals_snapshot,
                bull=state.bull_case.model_dump(),
                bear=state.bear_case.model_dump(),
            ),
            schema=DebateSummary.model_json_schema(),
            model=DebateSummary,
        )
        return {"debate_summary": debate}
    except Exception as e:
        lgr.warning("Debate failed; using fallback (%s)", type(e).__name__)
        return {
            "debate_summary": DebateSummary(
                bull=state.bull_case,
                bear=state.bear_case,
                synthesis=[f"Debate JSON parse failed; fallback used ({type(e).__name__})."],
                disagreements=[],
            )
        }


# ---------- final report patching ----------


def proposal_node(state: GraphState) -> dict[str, Any]:
    """
    Creates or patches the final fundamentals report.

    Phase 2:
      - Derive a single canonical TradeAction from stance/bias/confidence
        using decide_trade_action() (single source of truth).
      - Ensure stdout/JSON cleanliness by keeping debug behind trace.

    Contract notes:
      - FundamentalReport requires: ticker, snapshot, key_points (plus stance/bias/confidence).
      - Snapshot carries as_of/provider_stub via snapshot.quality.
    """
    enabled = bool(state.config.get("trace")) or bool(getattr(state, "trace_enabled", False))
    lgr = with_ctx(logger, LogCtx(node="proposal_node", ticker=state.ticker))

    def build_appendix() -> str | None:
        div_block = format_divergence_report(getattr(state, "divergence_report", None))
        agentic_block = _format_agentic_block(state)
        debate_block = _format_debate_block(state)
        appendix = _join_appendix(div_block, agentic_block, debate_block)
        return appendix or None

    def _min_conf() -> float:
        return float((state.config.get("trade_policy", {}) or {}).get("min_confidence", 0.55))

    # ---- Patch existing report if present ----
    if state.fundamentals_report is not None:
        rep = state.fundamentals_report
        updates: dict[str, Any] = {}

        if enabled:
            lgr.debug(
                "patching existing report: appendix_present=%s action_present=%s key_points_len=%s",
                bool(getattr(rep, "appendix", None)),
                getattr(rep, "action", None) is not None,
                len(list(getattr(rep, "key_points", []) or [])),
            )

        # Phase 2: action/action_reason (only if missing)
        if getattr(rep, "action", None) is None:
            decision = decide_trade_action(
                stance=rep.stance,
                bias=rep.covered_call_bias,
                confidence=float(rep.confidence),
                min_confidence=_min_conf(),
            )
            updates["action"] = decision.action
            updates["action_reason"] = decision.reason

        # Appendix patch (only if missing/empty)
        appendix = getattr(rep, "appendix", None)
        if appendix is None or (isinstance(appendix, str) and not appendix.strip()):
            new_appendix = build_appendix()
            if new_appendix:
                updates["appendix"] = new_appendix

        if not updates:
            return {}

        # Prefer model_copy for pydantic models (immutable-friendly)
        if hasattr(rep, "model_copy"):
            return {"fundamentals_report": rep.model_copy(update=updates)}

        # Fallback: best-effort mutation
        for k, v in updates.items():
            setattr(rep, k, v)
        return {}

    # ---- Create report if missing ----
    view = (
        getattr(state, "final_fundamentals", None)
        or getattr(state, "llm_fundamentals", None)
        or getattr(state, "det_fundamentals", None)
    )
    if view is None:
        raise RuntimeError("proposal_node: no fundamentals view available to build report")

    snap = getattr(state, "fundamentals_snapshot", None)
    if snap is None:
        raise RuntimeError("proposal_node: fundamentals_snapshot is None (required for FundamentalReport)")

    decision = decide_trade_action(
        stance=view.stance,
        bias=view.covered_call_bias,
        confidence=float(view.confidence),
        min_confidence=_min_conf(),
    )

    # FundamentalReport expects key_points. Upstream payloads may call them key_points or bullets.
    kp = getattr(view, "key_points", None)
    bul = getattr(view, "bullets", None)

    key_points: list[str] = []
    if isinstance(kp, (list, tuple)):
        key_points = [str(x).strip() for x in kp if str(x).strip()]
    elif isinstance(bul, (list, tuple)):
        key_points = [str(x).strip() for x in bul if str(x).strip()]

    # --- FIX: better deterministic fallback sources in LLM mode ---
    # 1) Prefer state.det_fundamentals.key_points if available
    if not key_points:
        det_view = getattr(state, "det_fundamentals", None)
        det_kp = getattr(det_view, "key_points", None) if det_view is not None else None
        if isinstance(det_kp, (list, tuple)) and det_kp:
            key_points = [str(x).strip() for x in det_kp if str(x).strip()]

    # 2) Next, fall back to an existing deterministic report if it exists on state
    #    (this covers cases where the deterministic node built a report earlier)
    if not key_points:
        existing_rep = getattr(state, "fundamentals_report", None)
        rep_kp = getattr(existing_rep, "key_points", None) if existing_rep is not None else None
        if isinstance(rep_kp, (list, tuple)) and rep_kp:
            key_points = [str(x).strip() for x in rep_kp if str(x).strip()]

    # 3) Last resort: synthesize from snapshot (be None-safe; stubs may not populate fields)
    if not key_points:
        def _fmt_pct(v: Any, decimals: int = 1) -> str:
            try:
                return f"{float(v):.{decimals}f}%"
            except Exception:
                return "—"

        def _fmt_num(v: Any, decimals: int = 2) -> str:
            try:
                return f"{float(v):.{decimals}f}"
            except Exception:
                return "—"

        rg = _fmt_pct(getattr(snap, "revenue_growth_yoy_pct", None), decimals=1)
        om = _fmt_pct(getattr(snap, "operating_margin_pct", None), decimals=1)
        dte = _fmt_num(getattr(snap, "debt_to_equity", None), decimals=2)

        key_points = [
            f"Revenue growth YoY: {rg}",
            f"Operating margin: {om}",
            f"Debt-to-equity: {dte}",
            "Divergence detected: see appendix for LLM debate summary.",
        ]
        
    key_points = key_points[:4]

    if enabled:
        lgr.debug(
            "create report: view_type=%s view_has_kp=%s det_kp_len=%s rep_kp_len=%s final_kp_len=%s",
            type(view).__name__,
            isinstance(getattr(view, "key_points", None), (list, tuple)),
            len(list(getattr(getattr(state, "det_fundamentals", None), "key_points", []) or [])),
            len(list(getattr(getattr(state, "fundamentals_report", None), "key_points", []) or [])),
            len(key_points),
        )

    rep = FundamentalReport(
        ticker=state.ticker,
        snapshot=snap,
        stance=view.stance,
        covered_call_bias=view.covered_call_bias,
        confidence=float(view.confidence),
        key_points=key_points,
        risks=list(getattr(view, "risks", []) or []),
        action=decision.action,
        action_reason=decision.reason,
        appendix=build_appendix(),
    )

    return {"fundamentals_report": rep}
