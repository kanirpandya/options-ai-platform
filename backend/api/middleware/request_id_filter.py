"""
backend.api.logging.request_id_filter

Purpose:
    Logging filter that injects request_id from contextvars into log records.

Author:
    Kanir Pandya
Created:
    2026-02-15
"""

from __future__ import annotations

import logging

from backend.api.logging.request_context import request_id_ctx_var


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get() or "-"
        return True
