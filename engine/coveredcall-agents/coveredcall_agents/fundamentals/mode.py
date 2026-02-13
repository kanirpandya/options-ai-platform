# coveredcall_agents/fundamentals/mode.py
# Purpose: FundamentalsMode enum + normalization helper.

from __future__ import annotations

from enum import Enum
from typing import Union


class FundamentalsMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    AGENTIC = "agentic"


def normalize_fundamentals_mode(mode: Union[str, FundamentalsMode, None]) -> FundamentalsMode:
    # Already normalized
    if isinstance(mode, FundamentalsMode):
        return mode

    # None => default
    if mode is None:
        return FundamentalsMode.DETERMINISTIC

    # Strings (CLI/config)
    if isinstance(mode, str):
        m = mode.strip().lower()
        if m in ("deterministic", "det"):
            return FundamentalsMode.DETERMINISTIC
        if m == "llm":
            return FundamentalsMode.LLM
        if m in ("agentic", "llm_agentic"):
            return FundamentalsMode.AGENTIC

    raise ValueError(f"Unknown fundamentals mode: {mode!r}")
