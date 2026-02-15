# backend/api/contracts/config_mapping.py
"""
backend.api.contracts.config_mapping

Purpose:
    Defines how API request fields map into engine DEFAULT_CONFIG structure.
    Avoids hard-coded nested keys inside route handlers.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigPaths:
    """
    Candidate paths (in priority order). We set the first path whose container exists;
    otherwise we fall back to the first candidate.
    """

    fundamentals_provider_candidates: tuple[tuple[str, ...], ...] = (
        ("providers", "fundamentals"),
        ("fundamentals", "provider"),
    )

    fundamentals_mode_candidates: tuple[tuple[str, ...], ...] = (
        ("fundamentals", "mode"),
        ("providers", "fundamentals_mode"),
    )

    debate_force_candidates: tuple[tuple[str, ...], ...] = (
        ("debate", "force_debate"),
        ("debate", "force"),
    )
