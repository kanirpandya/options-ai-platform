"""
backend.api.logging.logging_config

Purpose:
    Central logging configuration for backend API.
    Ensures request_id is present in logs (including uvicorn.access and uvicorn.error).

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

import logging

from backend.api.logging.request_id_filter import RequestIdFilter


def _make_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | request_id=%(request_id)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def _configure_logger(logger_name: str, handler: logging.Handler, *, clear_handlers: bool) -> None:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if clear_handlers:
        logger.handlers.clear()

    logger.addHandler(handler)
    logger.propagate = False


def configure_logging() -> None:
    handler = _make_handler()

    # Root/app logs (don’t clear root handlers to avoid surprising other libs)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    # Uvicorn uses these loggers; clear their handlers so our formatter/filter wins.
    _configure_logger("uvicorn", handler, clear_handlers=True)
    _configure_logger("uvicorn.error", handler, clear_handlers=True)
    _configure_logger("uvicorn.access", handler, clear_handlers=True)
