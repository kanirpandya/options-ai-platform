from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from coveredcall_agents.agentic.agentic_contracts import (
    AgenticAction,
    AgenticResponse,
    ToolResult,
    extract_first_json,
)
from coveredcall_agents.graph.state import CoveredCallBias, FundamentalsView, Stance
from coveredcall_agents.tools.agentic_tools import dispatch_agentic_tool
from coveredcall_agents.utils.logging import get_logger, with_ctx, LogCtx

MAX_TURNS = 3
MAX_TOOL_CALLS = 2

logger = get_logger(__name__)

AGENTIC_SYSTEM = """\
You are an investing assistant running in a bounded tool-calling loop.
...
"""


def _user_prompt(context: Dict[str, Any]) -> str:
    return f"""\
You MUST output a single JSON object that matches the schema.
...
""".strip()


def _coerce_stance(x: Any) -> Stance:
    if isinstance(x, Stance):
        return x
    if x is None:
        return Stance.NEUTRAL
    s = str(x).strip().upper()
    if s in ("BULLISH", "BULL", "LONG", "BUY"):
        return Stance.BULLISH
    if s in ("BEARISH", "BEAR", "SHORT", "SELL"):
        return Stance.BEARISH
    return Stance.NEUTRAL


def _coerce_bias(x: Any) -> CoveredCallBias:
    if isinstance(x, CoveredCallBias):
        return x
    if x is None:
        return CoveredCallBias.INCOME
    s = str(x).strip().upper()
    if s in ("UPSIDE", "UP", "GROWTH"):
        return CoveredCallBias.UPSIDE
    if s in ("CAUTION", "DEFENSIVE", "RISK_OFF"):
        return CoveredCallBias.CAUTION
    return CoveredCallBias.INCOME


def _has_min_numeric_grounding(resp: AgenticResponse) -> bool:
    bullets = list(getattr(resp, "bullets", []) or [])
    joined = " ".join(str(b) for b in bullets)
    digit_count = sum(1 for ch in joined if ch.isdigit())
    return digit_count >= 2


def agentic_node(state) -> dict:
    # Idempotent
    if getattr(state, "agentic_result", None) is not None:
        return {}

    if state.llm is None:
        raise RuntimeError("agentic_node: state.llm missing")

    lgr = with_ctx(
        logger,
        LogCtx(node="agentic_node", ticker=getattr(state, "ticker", None)),
    )

    tool_history: List[Dict[str, Any]] = []
    tool_calls = 0
    last_error: Optional[str] = None

    context: Dict[str, Any] = {
        "ticker": getattr(state, "ticker", None),
        "as_of": str(getattr(state, "as_of", "")),
        "has_snapshot": getattr(state, "fundamentals_snapshot", None) is not None,
        "has_scoring": getattr(state, "scoring", None) is not None,
        "tool_history": tool_history,
    }

    snap = getattr(state, "fundamentals_snapshot", None)
    if snap is not None:
        context["snapshot"] = snap.model_dump() if hasattr(snap, "model_dump") else snap

    use_text = hasattr(state.llm, "generate_text") and callable(getattr(state.llm, "generate_text"))
    schema = AgenticResponse.model_json_schema()

    for _turn in range(MAX_TURNS):
        if last_error:
            context["last_error"] = last_error
        else:
            context.pop("last_error", None)

        try:
            if use_text:
                raw = state.llm.generate_text(
                    system=AGENTIC_SYSTEM,
                    user=_user_prompt(context),
                )
                if not raw:
                    raise RuntimeError("LLM returned empty response")

                json_str = extract_first_json(raw)
                payload = json.loads(json_str)

                if isinstance(payload, dict) and "action" not in payload:
                    last_error = (
                        "Your JSON is missing required field 'action'. "
                        "Do NOT echo CONTEXT; output an AgenticResponse object."
                    )
                    lgr.debug("repair_needed=%s raw_trunc=%s", last_error, raw[:400])
                    continue

                resp: AgenticResponse = AgenticResponse.model_validate(payload)

            else:
                resp = state.llm.generate_json(
                    system=AGENTIC_SYSTEM,
                    user=_user_prompt(context),
                    schema=schema,
                    model=AgenticResponse,
                )

        except Exception as e:
            last_error = f"LLM error: {e}"
            lgr.debug("llm_error=%s", last_error)
            continue

        if resp.action == AgenticAction.CALL_TOOL:
            if resp.tool_call is None:
                last_error = "CALL_TOOL requires tool_call"
                continue
            if tool_calls >= MAX_TOOL_CALLS:
                last_error = "Tool call limit reached"
                continue

            tool_calls += 1
            tr: ToolResult = dispatch_agentic_tool(state, resp.tool_call)
            tool_history.append(tr.model_dump())

            context["tool_history"] = tool_history
            last_error = None
            continue

        if resp.action in (AgenticAction.PROPOSE, AgenticAction.ABSTAIN):
            if resp.action == AgenticAction.PROPOSE and snap is not None:
                if not _has_min_numeric_grounding(resp):
                    last_error = (
                        "Your PROPOSE must cite at least two snapshot numbers in bullets "
                        "(e.g., Revenue YoY %, Operating margin %, Debt-to-equity, Price)."
                    )
                    continue

            fv = FundamentalsView(
                stance=_coerce_stance(getattr(resp, "stance", None)),
                covered_call_bias=_coerce_bias(getattr(resp, "covered_call_bias", None)),
                confidence=float(getattr(resp, "confidence", 0.5) or 0.5),
                key_points=list(getattr(resp, "bullets", []) or []),
                risks=list(getattr(resp, "risks", []) or []),
            )

            return {
                "agentic_result": resp,
                "agentic_tool_history": tool_history,
                "agentic_fundamentals": fv,
                "llm_fundamentals": fv,
            }

        last_error = f"Unknown action: {resp.action}"

    fallback = AgenticResponse(
        action=AgenticAction.ABSTAIN,
        summary="Agentic loop failed; defaulting to ABSTAIN.",
        confidence=0.0,
        stance=None,
        covered_call_bias=None,
        bullets=[],
        risks=[
            "LLM output failed validation or exceeded limits.",
            *([last_error] if last_error else []),
        ],
    )

    fv = FundamentalsView(
        stance=Stance.NEUTRAL,
        covered_call_bias=CoveredCallBias.INCOME,
        confidence=0.0,
        key_points=[],
        risks=list(fallback.risks or []),
    )

    return {
        "agentic_result": fallback,
        "agentic_tool_history": tool_history,
        "agentic_fundamentals": fv,
        "llm_fundamentals": fv,
    }
