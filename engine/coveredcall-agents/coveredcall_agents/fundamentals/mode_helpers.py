# Purpose: Canonical helpers for fundamentals mode normalization.
from __future__ import annotations

from typing import Any, Mapping

from .mode import FundamentalsMode, normalize_fundamentals_mode


def get_fundamentals_mode(cfg: Mapping[str, Any]) -> FundamentalsMode:
    fcfg = (cfg.get("fundamentals", {}) or {})
    raw = (
        fcfg.get("mode")
        or cfg.get("fundamentals_mode")
        or cfg.get("mode")
        or FundamentalsMode.DETERMINISTIC
    )
    return normalize_fundamentals_mode(raw)
