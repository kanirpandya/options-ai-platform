# coveredcall_agents/agents/mode_accessors.py
# Purpose: Graph node that selects the final fundamentals decision (det vs llm vs agentic) using enum-native policy.

from __future__ import annotations

from coveredcall_agents.utils.logging import LogCtx, get_logger, with_ctx

from ..fundamentals.final_resolver import resolve_final_fundamentals
from ..fundamentals.mode_helpers import get_fundamentals_mode
from ..graph.state import GraphState

logger = get_logger(__name__)


def fundamentals_resolver_node(state: GraphState) -> dict:
    if getattr(state, "final_fundamentals", None) is not None:
        return {}

    cfg = (state.config or {}) if getattr(state, "config", None) else {}
    fcfg = cfg.get("fundamentals", {}) or {}

    mode = get_fundamentals_mode(cfg)  # Enum
    force_debate = bool(fcfg.get("force_debate", False) or cfg.get("force_debate", False))

    det = getattr(state, "det_fundamentals", None)
    llm = getattr(state, "llm_fundamentals", None)
    agentic = getattr(state, "agentic_fundamentals", None)

    lgr = with_ctx(
        logger,
        LogCtx(
            node="fundamentals_resolver_node",
            ticker=getattr(state, "ticker", None),
            mode=getattr(mode, "value", str(mode)),
        ),
    )

    lgr.debug("inputs det=%s llm=%s agentic=%s", det is not None, llm is not None, agentic is not None)

    decision = resolve_final_fundamentals(
        mode=mode,
        det=det,
        llm=llm,
        agentic=agentic,
        divergence_report=getattr(state, "divergence_report", None),
        force_debate=force_debate,
    )

    if decision is None:
        raise RuntimeError("fundamentals_resolver_node: resolver returned None (bug)")

    return {"final_fundamentals": decision}
