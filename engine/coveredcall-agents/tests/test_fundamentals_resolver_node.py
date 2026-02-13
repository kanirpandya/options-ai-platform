from __future__ import annotations

from types import SimpleNamespace

from coveredcall_agents.agents.mode_accessors import fundamentals_resolver_node
from coveredcall_agents.graph.state import CoveredCallBias, Stance


def test_fundamentals_resolver_node_sets_state_once():
    det = SimpleNamespace(
        stance=Stance.BULLISH,
        covered_call_bias=CoveredCallBias.UPSIDE,
        confidence=0.8,
    )

    state = SimpleNamespace(
        config={"fundamentals": {"mode": "deterministic"}, "force_debate": False},
        det_fundamentals=det,
        llm_fundamentals=None,
        agentic_fundamentals=None,
        divergence_report=None,
        final_fundamentals=None,
        trace_enabled=False,
    )

    out1 = fundamentals_resolver_node(state)
    assert out1["final_fundamentals"].stance == Stance.BULLISH

    state2 = SimpleNamespace(**{**state.__dict__, **out1})
    out2 = fundamentals_resolver_node(state2)
    assert out2 == {}
