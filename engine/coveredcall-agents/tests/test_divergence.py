"""
Unit tests for divergence scoring and classification logic.

Purpose:
- Validates divergence score calculations between deterministic and LLM views.
- Ensures severity bands and stance/bias differences are computed correctly.
- Guards against accidental changes to divergence semantics.
"""

from __future__ import annotations

from types import SimpleNamespace

from coveredcall_agents.agents.divergence_node import divergence_node
from coveredcall_agents.utils.divergence import compute_divergence, divergence_severity



def mk(stance: str, bias: str, conf: float):
    return SimpleNamespace(stance=stance, covered_call_bias=bias, confidence=conf)


def test_compute_divergence_aligned():
    det = mk("BULLISH", "INCOME", 0.70)
    llm = mk("BULLISH", "INCOME", 0.72)
    r = compute_divergence(det, llm)
    assert 0.0 <= r.score <= 0.2
    assert r.severity in ("ALIGNED", "MINOR")  # should be ALIGNED for this case


def test_compute_divergence_major():
    det = mk("BULLISH", "INCOME", 0.80)
    llm = mk("NEUTRAL", "CAUTION", 0.30)  # stance & bias shift + conf gap
    r = compute_divergence(det, llm)
    assert r.score >= 0.40
    assert r.severity in ("MAJOR", "CRITICAL")


def test_compute_divergence_critical_extreme():
    det = mk("BULLISH", "UPSIDE", 0.95)
    llm = mk("BEARISH", "CAUTION", 0.10)  # maximum stance jump, bias jump, big conf gap
    r = compute_divergence(det, llm)
    assert r.score > 0.65
    assert r.severity == "CRITICAL"


def test_divergence_severity_bands():
    assert divergence_severity(0.00) == "ALIGNED"
    assert divergence_severity(0.19) == "ALIGNED"
    assert divergence_severity(0.20) == "MINOR"
    assert divergence_severity(0.39) == "MINOR"
    assert divergence_severity(0.40) == "MAJOR"
    assert divergence_severity(0.64) == "MAJOR"
    assert divergence_severity(0.65) == "CRITICAL"


def test_divergence_node_sets_report():
    state = {
        "det_fundamentals": mk("BULLISH", "INCOME", 0.75),
        "llm_fundamentals": mk("NEUTRAL", "INCOME", 0.55),
    }
    out = divergence_node(state)
    assert "divergence_report" in out
    rep = out["divergence_report"]
    # pydantic model expected
    assert hasattr(rep, "severity")
    assert rep.severity in ("ALIGNED", "MINOR", "MAJOR", "CRITICAL")


def test_divergence_node_missing_inputs_non_blocking():
    state = {"det_fundamentals": mk("BULLISH", "INCOME", 0.75)}
    out = divergence_node(state)
    rep = out["divergence_report"]
    assert rep.notes is not None
    assert rep.severity == "ALIGNED"
