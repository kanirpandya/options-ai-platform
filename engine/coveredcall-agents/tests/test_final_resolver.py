"""
tests/test_final_resolver.py

Purpose:
- Locks final fundamentals selection policy in resolve_final_fundamentals().
"""

from __future__ import annotations

from types import SimpleNamespace

from coveredcall_agents.fundamentals.final_resolver import resolve_final_fundamentals
from coveredcall_agents.fundamentals.mode import FundamentalsMode
from coveredcall_agents.graph.state import CoveredCallBias, FinalSource, Stance


def mk_out(stance: Stance, bias: CoveredCallBias, conf: float):
    return SimpleNamespace(stance=stance, covered_call_bias=bias, confidence=conf)


def mk_div(severity: str):
    return SimpleNamespace(severity=severity)


def test_agentic_mode_prefers_agentic_when_present():
    det = mk_out(Stance.BULLISH, CoveredCallBias.UPSIDE, 0.8)
    agentic = mk_out(Stance.BEARISH, CoveredCallBias.CAUTION, 0.7)

    d = resolve_final_fundamentals(
        mode=FundamentalsMode.AGENTIC,
        det=det,
        llm=None,
        agentic=agentic,
        divergence_report=None,
        force_debate=False,
    )

    assert d.source == FinalSource.AGENTIC
    assert d.stance == Stance.BEARISH


def test_aligned_prefers_deterministic():
    det = mk_out(Stance.BULLISH, CoveredCallBias.UPSIDE, 0.8)
    llm = mk_out(Stance.NEUTRAL, CoveredCallBias.INCOME, 0.6)

    d = resolve_final_fundamentals(
        mode=FundamentalsMode.LLM,
        det=det,
        llm=llm,
        agentic=None,
        divergence_report=mk_div("ALIGNED"),
        force_debate=True,
    )

    assert d.source == FinalSource.DETERMINISTIC
    assert d.stance == Stance.BULLISH


def test_major_divergence_force_debate_prefers_llm():
    det = mk_out(Stance.BULLISH, CoveredCallBias.UPSIDE, 0.8)
    llm = mk_out(Stance.BEARISH, CoveredCallBias.CAUTION, 0.8)

    d = resolve_final_fundamentals(
        mode=FundamentalsMode.LLM,
        det=det,
        llm=llm,
        agentic=None,
        divergence_report=mk_div("MAJOR"),
        force_debate=True,
    )

    assert d.source == FinalSource.LLM
    assert d.stance == Stance.BEARISH


def test_major_divergence_without_force_debate_falls_back_to_det():
    det = mk_out(Stance.BULLISH, CoveredCallBias.UPSIDE, 0.8)
    llm = mk_out(Stance.BEARISH, CoveredCallBias.CAUTION, 0.8)

    d = resolve_final_fundamentals(
        mode=FundamentalsMode.LLM,
        det=det,
        llm=llm,
        agentic=None,
        divergence_report=mk_div("MAJOR"),
        force_debate=False,
    )

    assert d.source == FinalSource.DETERMINISTIC
    assert d.stance == Stance.BULLISH


def test_fallback_order_when_no_divergence():
    llm = mk_out(Stance.NEUTRAL, CoveredCallBias.INCOME, 0.6)

    d = resolve_final_fundamentals(
        mode=FundamentalsMode.LLM,
        det=None,
        llm=llm,
        agentic=None,
        divergence_report=None,
        force_debate=False,
    )

    assert d.source == FinalSource.LLM
    assert d.stance == Stance.NEUTRAL
