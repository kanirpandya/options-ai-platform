# coveredcall_agents/graph/nodes/llm_node.py
# Purpose: LLM fundamentals node with stderr-only logging + safe fallback (keeps --output json stdout-pure).

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..graph.state import CoveredCallBias, FundamentalsView, GraphState, Stance
from ..llm.debate_prompts import snapshot_block
from ..utils.logging import LogCtx, get_logger, with_ctx


class LLMFundamentalsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: float = Field(ge=0.0, le=1.0)
    bullets: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


LLM_NODE_SYSTEM = """
You are a fundamentals advisor.

You MUST return ONLY valid JSON that conforms to the provided JSON schema.

Hard rules:
- Output ONLY a JSON object (no markdown, no prose).
- Use ONLY these keys: stance, covered_call_bias, confidence, bullets, risks
- stance MUST be one of: "BULLISH", "NEUTRAL", "BEARISH"
- covered_call_bias MUST be one of: "UPSIDE", "INCOME", "CAUTION" (string, NOT a number)
- confidence MUST be a number between 0.0 and 1.0
- bullets MUST be an array of strings (2-4 items)
- risks MUST be an array of strings (0-2 items)
- Do NOT use objects inside bullets/risks arrays.
- Do NOT include extra keys (no fundamentals_stance, no short_bullets, etc.)
- Do NOT include literal newline characters inside JSON string values; use \\n if needed.
"""

LLM_NODE_USER_TEMPLATE = """\
SNAPSHOT (ground truth; do not invent numbers):
{snapshot}

Return ONLY a single JSON object (no markdown, no extra text).
Use ONLY these keys: stance, covered_call_bias, confidence, bullets, risks.

Allowed values:
- stance: BULLISH | NEUTRAL | BEARISH  (choose ONE of these exact strings)
- covered_call_bias: UPSIDE | INCOME | CAUTION  (choose ONE of these exact strings)

Constraints:
- confidence: number between 0.0 and 1.0
- bullets: array of 2-4 short strings
- risks: array of 0-2 short strings
- Do NOT output any '|' characters in values.
- Do NOT include objects inside bullets/risks arrays.

Notes:
- Use "—" if a point depends on missing fundamentals.
"""


def _fallback_from_det(state: GraphState, *, reason: str) -> FundamentalsView:
    det = getattr(state, "det_fundamentals", None)
    fallback = det or FundamentalsView(
        stance=Stance.NEUTRAL,
        covered_call_bias=CoveredCallBias.INCOME,
        confidence=0.30,
        key_points=["LLM fundamentals unavailable; proceeding without it."],
        risks=[],
    )

    # Make it obviously degraded (cap confidence)
    return fallback.model_copy(update={"confidence": min(float(fallback.confidence), 0.60)})


def llm_node(state: GraphState) -> dict:
    if state.llm_fundamentals is not None:
        return {}
    if state.fundamentals_snapshot is None:
        raise RuntimeError("llm_node: fundamentals_snapshot missing")
    if state.llm is None:
        # If mode=llm but no provider configured, be non-fatal and proceed.
        return {}

    base_logger = get_logger(__name__)
    lgr = with_ctx(
        base_logger,
        LogCtx(
            node="llm_node",
            ticker=getattr(state, "ticker", None),
            mode=str(getattr(state, "fundamentals_mode", None) or getattr(state, "mode", None) or ""),
        ),
    )

    schema = LLMFundamentalsPayload.model_json_schema()
    user = LLM_NODE_USER_TEMPLATE.format(snapshot=snapshot_block(state.fundamentals_snapshot))

    try:
        lgr.debug("Calling LLM fundamentals")
        payload = state.llm.generate_json(
            system=LLM_NODE_SYSTEM,
            user=user,
            schema=schema,
            model=LLMFundamentalsPayload,
        )

        view = FundamentalsView(
            stance=payload.stance,
            covered_call_bias=payload.covered_call_bias,
            confidence=float(payload.confidence),
            key_points=list(payload.bullets or [])[:4],
            risks=list(payload.risks or [])[:2],
        )

        lgr.debug(
            "LLM fundamentals ok stance=%s bias=%s conf=%.2f",
            view.stance,
            view.covered_call_bias,
            view.confidence,
        )
        return {"llm_fundamentals": view}

    except httpx.TimeoutException:
        lgr.warning("LLM timeout — using fallback")
        return {"llm_fundamentals": _fallback_from_det(state, reason="timeout")}

    except (ValidationError, ValueError, TypeError) as e:
        # Schema/parse issues should never break stdout JSON mode
        lgr.warning("LLM schema/parse failure — using fallback (%s)", e.__class__.__name__)
        return {"llm_fundamentals": _fallback_from_det(state, reason="parse")}

    except Exception:
        # Keep a traceback on stderr for debugging, never stdout
        lgr.exception("LLM failure — using fallback")
        return {"llm_fundamentals": _fallback_from_det(state, reason="exception")}
