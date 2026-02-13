# coveredcall_agents/fundamentals/final_resolver.py
# Purpose: Select the final fundamentals stance/bias/confidence using a conservative policy across modes (det/llm/agentic) + divergence + force_debate.

from __future__ import annotations

from typing import Any, Optional

from ..graph.state import FinalFundamentalsDecision, FinalSource
from .mode import FundamentalsMode


def resolve_final_fundamentals(
    *,
    mode: FundamentalsMode,
    det: Optional[Any],
    llm: Optional[Any],
    agentic: Optional[Any],
    divergence_report: Optional[Any],
    force_debate: bool,
) -> FinalFundamentalsDecision:
    """
    Policy (conservative baseline):
    1) If mode == AGENTIC and agentic exists -> agentic wins.
    2) If divergence severity is ALIGNED or MINOR -> deterministic wins (if present),
       even if force_debate=True (force_debate is about running debate/appendix).
    3) If force_debate and llm exists -> LLM wins (when not aligned/minor).
    4) If divergence severity is MAJOR/CRITICAL and force_debate -> LLM wins (if present).
       (Usually covered by rule #3, but retained for rationale completeness.)
    5) Fallback order: deterministic -> LLM -> agentic (whichever exists).
    """

    def _severity(dr: Optional[Any]) -> str:
        if dr is None:
            return "UNKNOWN"
        sev = getattr(dr, "severity", None)
        if sev is None:
            return "UNKNOWN"
        return str(getattr(sev, "value", sev)).upper()

    severity = _severity(divergence_report)

    def _mk(src: FinalSource, picked: Any, why: str) -> FinalFundamentalsDecision:
        return FinalFundamentalsDecision(
            stance=picked.stance,
            covered_call_bias=picked.covered_call_bias,
            confidence=float(picked.confidence),
            source=src,
            rationale=why,
        )

    # 1) Agentic mode: prefer agentic output if present
    if mode == FundamentalsMode.AGENTIC and agentic is not None:
        return _mk(FinalSource.AGENTIC, agentic, f"mode=agentic; agentic present; severity={severity}")

    # 2) Aligned/minor divergence: deterministic wins (if present)
    if severity in {"ALIGNED", "MINOR"} and det is not None:
        return _mk(FinalSource.DETERMINISTIC, det, f"severity={severity}; prefer deterministic")

    # 3) Force debate: prefer LLM when present (only when not aligned/minor)
    if force_debate and llm is not None:
        return _mk(FinalSource.LLM, llm, f"force_debate; using llm; severity={severity}")

    # 4) Major/critical divergence + force_debate: LLM wins (if present)
    if severity in {"MAJOR", "CRITICAL"} and force_debate and llm is not None:
        return _mk(FinalSource.LLM, llm, f"severity={severity} + force_debate; using llm")

    # 5) Fallback order
    if det is not None:
        return _mk(FinalSource.DETERMINISTIC, det, f"fallback deterministic; severity={severity}")
    if llm is not None:
        return _mk(FinalSource.LLM, llm, f"fallback llm; severity={severity}")
    if agentic is not None:
        return _mk(FinalSource.AGENTIC, agentic, f"fallback agentic; severity={severity}")

    raise RuntimeError("resolve_final_fundamentals: no fundamentals inputs available")
