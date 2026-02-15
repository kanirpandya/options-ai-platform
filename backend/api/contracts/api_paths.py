# backend/api/contracts/api_paths.py
"""
backend.api.contracts.api_paths

Purpose:
    Central definition of API route paths and versioning.
    Keeps routing stable and prevents string duplication.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiPaths:
    v1_prefix: str = "/v1"
    health: str = "/health"
    analyze: str = "/analyze"
    analyze_debug: str = "/analyze/debug"
