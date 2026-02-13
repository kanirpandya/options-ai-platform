# tests/test_mode_normalization.py
"""
Purpose:
- Guardrail: ensure legacy alias strings remain supported (or fail loudly if removed).
"""

from coveredcall_agents.fundamentals.mode import FundamentalsMode, normalize_fundamentals_mode


def test_llm_agentic_alias_maps_to_agentic():
    assert normalize_fundamentals_mode("llm_agentic") == FundamentalsMode.AGENTIC


def test_det_alias_maps_to_deterministic():
    assert normalize_fundamentals_mode("det") == FundamentalsMode.DETERMINISTIC
