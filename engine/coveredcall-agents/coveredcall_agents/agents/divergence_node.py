from __future__ import annotations

from typing import Any, Dict, Union

from coveredcall_agents.utils.divergence import compute_divergence
from coveredcall_agents.utils.logging import LogCtx, get_logger, with_ctx

from ..graph.state import DivergenceReport, GraphState

logger = get_logger(__name__)


def _read(state: Union[GraphState, Dict[str, Any]], key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def divergence_node(state: Union[GraphState, Dict[str, Any]]) -> dict:
    det = _read(state, "det_fundamentals")
    other = _read(state, "agentic_fundamentals") or _read(state, "llm_fundamentals")

    cfg = _read(state, "config", {}) or {}
    fcfg = cfg.get("fundamentals", {}) or {}
    mode = fcfg.get("mode")

    lgr = with_ctx(
        logger,
        LogCtx(
            node="divergence_node",
            ticker=_read(state, "ticker", None),
            mode=mode,
        ),
    )

    lgr.debug("inputs det_fundamentals=%s", det is not None)
    lgr.debug("inputs llm/agentic_fundamentals=%s", other is not None)

    if det is None or other is None:
        rep = DivergenceReport(
            score=0.0,
            severity="ALIGNED",
            stance=("NEUTRAL", "NEUTRAL"),
            covered_call_bias=("INCOME", "INCOME"),
            confidence=(0.5, 0.5),
            stance_divergence=0.0,
            bias_divergence=0.0,
            confidence_divergence=0.0,
            action_hint="Proceed with deterministic recommendation",
            notes="det_fundamentals or (agentic_fundamentals/llm_fundamentals) missing",
        )
        return {"divergence_report": rep}

    rep = compute_divergence(det, other)
    return {"divergence_report": rep}
