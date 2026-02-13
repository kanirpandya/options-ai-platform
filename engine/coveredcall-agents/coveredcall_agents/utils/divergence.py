from __future__ import annotations

from typing import Any

from ..graph.state import DivergenceReport


def divergence_severity(score: float) -> str:
    if score < 0.20:
        return "ALIGNED"
    if score < 0.40:
        return "MINOR"
    if score < 0.65:
        return "MAJOR"
    return "CRITICAL"


def action_hint(severity: str) -> str:
    return {
        "ALIGNED": "Proceed with deterministic recommendation",
        "MINOR": "Proceed but annotate LLM nuance",
        "MAJOR": "Surface both views to user (or trigger debate)",
        "CRITICAL": "Require manual review or run debate/second pass",
    }[severity]


def compute_divergence(det: Any, llm: Any) -> DivergenceReport:
    """
    det, llm are expected to have:
      - stance: str
      - covered_call_bias: str
      - confidence: float (0..1)
    Missing/unknown values degrade gracefully to NEUTRAL/INCOME/0.5.
    """
    stance_map = {"BEARISH": -1, "NEUTRAL": 0, "BULLISH": 1}
    bias_map = {"CAUTION": -1, "INCOME": 0, "UPSIDE": 1}

    det_stance = getattr(det, "stance", "NEUTRAL") or "NEUTRAL"
    llm_stance = getattr(llm, "stance", "NEUTRAL") or "NEUTRAL"
    det_bias = getattr(det, "covered_call_bias", "INCOME") or "INCOME"
    llm_bias = getattr(llm, "covered_call_bias", "INCOME") or "INCOME"

    det_conf = float(getattr(det, "confidence", 0.5) or 0.5)
    llm_conf = float(getattr(llm, "confidence", 0.5) or 0.5)

    s_det = stance_map.get(det_stance, 0)
    s_llm = stance_map.get(llm_stance, 0)
    b_det = bias_map.get(det_bias, 0)
    b_llm = bias_map.get(llm_bias, 0)

    # Normalize each dimension to 0..1
    stance_div = abs(s_det - s_llm) / 2.0
    bias_div = abs(b_det - b_llm) / 2.0
    conf_div = min(abs(det_conf - llm_conf), 0.5) / 0.5

    score = 0.45 * stance_div + 0.30 * bias_div + 0.25 * conf_div

    score = max(0.0, min(1.0, score))
    sev = divergence_severity(score)

    return DivergenceReport(
        score=round(score, 3),
        severity=sev,
        stance=(det_stance, llm_stance),
        covered_call_bias=(det_bias, llm_bias),
        confidence=(round(det_conf, 3), round(llm_conf, 3)),
        stance_divergence=round(stance_div, 3),
        bias_divergence=round(bias_div, 3),
        confidence_divergence=round(conf_div, 3),
        action_hint=action_hint(sev),
    )

def format_divergence_report(rep: Any) -> str:
    """Return a human-readable divergence block for CLI/report output."""
    if rep is None:
        return ""

    d = rep.model_dump() if hasattr(rep, "model_dump") else dict(rep)

    stance = d.get("stance") or ("?", "?")
    bias = d.get("covered_call_bias") or ("?", "?")
    conf = d.get("confidence") or ("?", "?")

    return (
        "DIVERGENCE REPORT\n"
        "-----------------\n"
        f"Score:      {d.get('score')}\n"
        f"Severity:   {d.get('severity')}\n\n"
        f"Stance:     DET={stance[0]} | LLM={stance[1]}\n"
        f"Bias:       DET={bias[0]}  | LLM={bias[1]}\n"
        f"Confidence: DET={conf[0]}  | LLM={conf[1]}\n\n"
        f"Action:     {d.get('action_hint')}\n"
        + (f"Notes:      {d.get('notes')}\n" if d.get("notes") else "")
    )
