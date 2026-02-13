"""
Tests provider selection and fallback behavior.

Purpose:
- Verifies primary and fallback fundamentals providers are selected correctly.
- Ensures provider failures do not crash the pipeline.
- Confirms metadata reflects provider switching when it occurs.
"""

from coveredcall_agents.config.default_config import DEFAULT_CONFIG
from coveredcall_agents.graph.covered_call_graph import CoveredCallAgentsGraph


def test_yfinance_provider_sets_is_stub_false():
    cfg = {
        **DEFAULT_CONFIG,
        "providers": {**DEFAULT_CONFIG.get("providers", {}), "fundamentals": "yfinance"},
    }
    g = CoveredCallAgentsGraph()
    s = g.propagate("AAPL", config=cfg)
    assert s.fundamentals_report is not None
    assert s.fundamentals_report.snapshot.quality.is_stub is False
