"""
backend.api.logging.request_context

Purpose:
    Request-scoped context storage using contextvars.
    Enables request_id propagation into logs.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

import contextvars

request_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)