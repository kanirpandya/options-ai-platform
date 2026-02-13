"""
coveredcall_agents/graph/covered_call_graph.py

Purpose:
- LangGraph wiring for the fundamentals pipeline.
- Routes execution based on fundamentals mode (deterministic / llm / agentic).
- Always runs divergence + debate for llm/agentic (Policy B), then resolves final fundamentals,
  then generates the final proposal/report.
"""

from datetime import datetime
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from coveredcall_agents.utils.logging import LogCtx, get_logger, with_ctx

from ..agents.agentic_node import agentic_node
from ..agents.debate_agents import bear_node, bull_node, debate_node, proposal_node
from ..agents.divergence_node import divergence_node
from ..agents.fundamental_agent import fundamental_node
from ..agents.mode_accessors import fundamentals_resolver_node
from ..agents.llm_node import llm_node
from ..fundamentals.mode import FundamentalsMode
from ..fundamentals.mode_helpers import get_fundamentals_mode
from ..llm.client import OllamaClient
from ..llm.mock_client import MockLLMClient
from ..tools.fundamentals import get_fundamental_snapshot
from ..tools.fundamentals_yfinance import get_fundamental_snapshot_yfinance
from ..tools.registry import Tools
from .node_ids import NodeId as N
from .state import GraphState

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Routing policy
# ---------------------------------------------------------------------------

def _cfg_from_state(state: Any) -> dict:
    if isinstance(state, dict):
        return state.get("config", {}) or {}
    return (getattr(state, "config", None) or {}) if hasattr(state, "config") else {}


def route_from_divergence(state: Any) -> str:
    """
    Policy B:
    - If mode is LLM or AGENTIC: always go through the debate fanout.
    - Otherwise (deterministic): go straight to fund_resolve.
    """
    cfg = _cfg_from_state(state)
    fcfg = cfg.get("fundamentals", {}) or {}

    mode = get_fundamentals_mode(cfg)

    lgr = with_ctx(
        logger,
        LogCtx(node="route_from_divergence", mode=getattr(mode, "value", str(mode))),
    )
    lgr.debug("fundamentals cfg=%s", fcfg)
    lgr.debug(
        "mode=%s force_debate=%s",
        getattr(mode, "value", str(mode)),
        bool(fcfg.get("force_debate", False)),
    )

    if mode in (FundamentalsMode.LLM, FundamentalsMode.AGENTIC):
        lgr.debug("-> %s (Policy B)", N.FANOUT_LLM.value)
        return N.FANOUT_LLM.value

    lgr.debug("-> %s (deterministic)", N.FUND_RESOLVE.value)
    return N.FUND_RESOLVE.value


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class CoveredCallAgentsGraph:
    def __init__(self) -> None:
        self._graph = self._build()

    def _build(self):
        g = StateGraph(GraphState)

        # Stage 1: snapshot + deterministic fundamentals
        g.add_node(N.FUNDAMENTAL.value, trace_node(N.FUNDAMENTAL.value, fundamental_node))

        # Stage 2: mode-specific producer
        g.add_node(N.DET.value, trace_node(N.DET.value, noop_node(N.DET.value)))
        g.add_node(N.LLM.value, trace_node(N.LLM.value, llm_node))
        g.add_node(N.AGENTIC.value, trace_node(N.AGENTIC.value, agentic_node))

        # Divergence
        g.add_node(N.DIVERGENCE.value, trace_node(N.DIVERGENCE.value, divergence_node))

        # Debate fanout
        g.add_node(N.FANOUT_LLM.value, trace_node(N.FANOUT_LLM.value, noop_node(N.FANOUT_LLM.value)))
        g.add_node(N.BULL.value, trace_node(N.BULL.value, bull_node))
        g.add_node(N.BEAR.value, trace_node(N.BEAR.value, bear_node))
        g.add_node(N.DEBATE.value, trace_node(N.DEBATE.value, debate_node))

        # Final resolution + proposal
        g.add_node(N.FUND_RESOLVE.value, trace_node(N.FUND_RESOLVE.value, fundamentals_resolver_node))
        g.add_node(N.PROPOSAL.value, trace_node(N.PROPOSAL.value, proposal_node))

        # Edges
        g.add_edge(START, N.FUNDAMENTAL.value)

        def route_after_fundamental(state: GraphState) -> str:
            cfg = (state.config or {}) if getattr(state, "config", None) else {}
            mode = get_fundamentals_mode(cfg)

            # Enum decision → NodeId wiring
            if mode == FundamentalsMode.AGENTIC:
                return N.AGENTIC.value
            if mode == FundamentalsMode.LLM:
                return N.LLM.value
            return N.DET.value

        g.add_conditional_edges(
            N.FUNDAMENTAL.value,
            route_after_fundamental,
            {
                N.LLM.value: N.LLM.value,
                N.AGENTIC.value: N.AGENTIC.value,
                N.DET.value: N.DET.value,
            },
        )

        # Deterministic → resolve
        g.add_edge(N.DET.value, N.FUND_RESOLVE.value)

        # LLM / agentic → divergence
        g.add_edge(N.LLM.value, N.DIVERGENCE.value)
        g.add_edge(N.AGENTIC.value, N.DIVERGENCE.value)

        g.add_conditional_edges(
            N.DIVERGENCE.value,
            route_from_divergence,
            {N.FANOUT_LLM.value: N.FANOUT_LLM.value, N.FUND_RESOLVE.value: N.FUND_RESOLVE.value},
        )

        # Fanout + join
        g.add_edge(N.FANOUT_LLM.value, N.BULL.value)
        g.add_edge(N.FANOUT_LLM.value, N.BEAR.value)
        g.add_edge(N.BULL.value, N.DEBATE.value)
        g.add_edge(N.BEAR.value, N.DEBATE.value)

        # Resolve → proposal → end
        g.add_edge(N.DEBATE.value, N.FUND_RESOLVE.value)
        g.add_edge(N.FUND_RESOLVE.value, N.PROPOSAL.value)
        g.add_edge(N.PROPOSAL.value, END)

        return g.compile()

    def propagate(self, ticker: str, config: dict, as_of: Optional[datetime] = None) -> GraphState:
        provider = (config.get("providers", {}) or {}).get("fundamentals", "stub")
        fn = get_fundamental_snapshot_yfinance if provider == "yfinance" else get_fundamental_snapshot
        tools = Tools(get_fundamental_snapshot=fn)

        mode = get_fundamentals_mode(config)

        llm_client: Any = None
        if mode in (FundamentalsMode.LLM, FundamentalsMode.AGENTIC):
            llm_cfg = config.get("llm", {}) or {}

            if llm_cfg.get("provider") == "mock":
                llm_client = MockLLMClient()

            elif llm_cfg.get("provider") == "ollama":
                llm_client = OllamaClient(
                    model_name=str(llm_cfg.get("model", "llama3.1:8b")),
                    base_url=str(llm_cfg.get("base_url", "http://localhost:11434")),
                    timeout_s=float(llm_cfg.get("timeout_s", 30.0)),
                    trace=bool(config.get("trace", False)),
                )

            elif llm_cfg.get("provider") in (None, "none"):
                llm_client = None
            else:
                raise ValueError(f"Unsupported LLM provider: {llm_cfg.get('provider')}")

            # IMPORTANT: fail early and clearly (prevents the old crash path)
            if llm_client is None:
                raise ValueError("LLM mode requires an LLM provider (e.g., --llm-provider ollama|mock).")

        init = GraphState(
            ticker=ticker,
            config=config,
            tools=tools,
            llm=llm_client,
        )
        if as_of is not None:
            init = init.model_copy(update={"as_of": as_of})

        out = self._graph.invoke(init)
        out_state = out if isinstance(out, GraphState) else GraphState.model_validate(out)

        lgr = with_ctx(logger, LogCtx(node="graph_output", ticker=ticker))
        lgr.debug("trace_nodes=%s", out_state.trace_nodes)
        lgr.debug("divergence_report=%s", out_state.divergence_report)
        lgr.debug("agentic_result=%s", out_state.agentic_result)
        lgr.debug("final_fundamentals=%s", out_state.final_fundamentals)

        return out_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def noop_node(name: str):
    def _noop(_state):
        return {}

    _noop.__name__ = f"noop_{name}"
    return _noop


def trace_node(name: str, fn):
    """
    Wraps a node to:
    - Always append trace_nodes metadata
    - Always emit DEBUG logs (visibility controlled centrally)
    """
    def _wrapped(state):
        out = fn(state)

        trace_updates = {"trace_nodes": [name]}
        lgr = with_ctx(logger, LogCtx(node=f"node:{name}"))
        lgr.debug("returned_keys=%s", list(out.keys()) if isinstance(out, dict) else type(out))

        if isinstance(out, dict):
            return {**out, **trace_updates}

        if hasattr(out, "model_copy"):
            return out.model_copy(update=trace_updates)

        return trace_updates or out

    return _wrapped
