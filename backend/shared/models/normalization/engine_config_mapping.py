"""
backend.shared.models.normalization.engine_config_mapping

Purpose:
    Centralized mapping/normalization utilities to translate API-level request values
    (human-friendly enums) into engine-native config values.

Why:
    Prevents drift between:
      - API schemas (e.g., "deterministic", "yahoo_stub")
      - Route override logic
      - Engine expectations (e.g., "det", "stub", "yfinance")

Usage:
    - backend.api.routes.v1.analysis uses apply_engine_overrides_from_request()
    - CLI and worker components can also call map_* functions directly

Author:
    Kanir Pandya

Created:
    2026-02-19
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# API provider names -> engine fundamentals provider names
_PROVIDER_MAP: Dict[str, str] = {
    "yahoo": "yfinance",
    "yahoo_stub": "stub",
    # allow passing engine-native values too
    "yfinance": "yfinance",
    "stub": "stub",
}

# API mode names -> engine mode names
_MODE_MAP: Dict[str, str] = {
    "deterministic": "det",
    "det": "det",
    "llm": "llm",
    "agentic": "agentic",
}


def _norm(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return s.lower()


def map_fundamentals_mode_to_engine(raw: Optional[str]) -> Optional[str]:
    """
    Map an API-level fundamentals mode string to an engine mode string.
    Unknown values pass through (normalized) to allow forward-compat / engine-native values.
    """
    v = _norm(raw)
    if v is None:
        return None
    return _MODE_MAP.get(v, v)


def map_fundamentals_provider_to_engine(raw: Optional[str]) -> Optional[str]:
    """
    Map an API-level fundamentals provider string to an engine fundamentals provider string.
    Unknown values pass through (normalized) to allow forward-compat / engine-native values.
    """
    v = _norm(raw)
    if v is None:
        return None
    return _PROVIDER_MAP.get(v, v)


def apply_engine_overrides_from_request(
    config: Dict[str, Any],
    *,
    provider: Optional[str],
    mode: Optional[str],
    force_debate: Optional[bool],
    output: Optional[str],
) -> Dict[str, Any]:
    """
    Apply API-level overrides to engine config using centralized mapping logic.
    """

    # Provider mapping
    if provider:
        engine_provider = map_fundamentals_provider_to_engine(provider)
        if engine_provider:
            config.setdefault("providers", {})["fundamentals"] = engine_provider
        config.pop("provider", None)

    # Mode mapping
    if mode:
        engine_mode = map_fundamentals_mode_to_engine(mode)
        if engine_mode:
            config["mode"] = engine_mode

    # Force debate
    if force_debate is not None:
        config["force_debate"] = force_debate

    # Output override
    if output:
        config["output"] = output

    return config
