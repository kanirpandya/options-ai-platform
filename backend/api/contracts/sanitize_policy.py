# backend/api/contracts/sanitize_policy.py
"""
backend.api.contracts.sanitize_policy

Purpose:
    Defines JSON sanitation conventions for API responses.
    Centralizes special token strings and depth limit.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SanitizePolicy:
    max_depth: int = 20
    max_depth_token: str = "<max_depth_exceeded>"
    callable_prefix: str = "<callable:"
    callable_suffix: str = ">"
