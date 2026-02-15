"""
backend.api.contracts.request_id_policy

Purpose:
    Central policy for request/correlation IDs (header names + response behavior).

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestIdPolicy:
    request_id_header: str = "X-Request-Id"
    correlation_id_header: str = "X-Correlation-Id"
    response_header: str = "X-Request-Id"
