"""
Smoke tests for the LangGraph execution pipeline.

Purpose:
- Confirms the graph can execute end-to-end for supported modes.
- Verifies required nodes produce expected state fields.
- Catches graph wiring or state propagation issues early.
"""

from coveredcall_agents.config.default_config import DEFAULT_CONFIG
from coveredcall_agents.graph.covered_call_graph import CoveredCallAgentsGraph


def test_propagate_returns_fundamental_report():
    g = CoveredCallAgentsGraph()
    s = g.propagate("AAPL", config=DEFAULT_CONFIG)

    assert s.fundamentals_report is not None
    assert s.fundamentals_report.ticker == "AAPL"
    assert s.fundamentals_report.stance in {"BULLISH", "NEUTRAL", "BEARISH"}
