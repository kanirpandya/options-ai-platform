# coveredcall_agents/utils/logging.py
# Purpose: Shared logging helpers (logger factory + adapters) for coveredcall-agents.
# Notes: CLI owns handler/format/level and routes logs to stderr. This module must never print.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping


# Stable logger name prefix so users can filter with `--log-level` and grep easily.
LOGGER_NAMESPACE = "coveredcall_agents"


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a namespaced logger. Does NOT configure handlers/levels.
    Configuration must be done by the CLI (stderr-only).
    """
    if not name:
        return logging.getLogger(LOGGER_NAMESPACE)

    # If caller passes __name__, keep it but ensure it is under our namespace.
    # e.g. "coveredcall_agents.graph.nodes.llm_node"
    if name.startswith(LOGGER_NAMESPACE):
        return logging.getLogger(name)

    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")


class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    Prefix log messages with stable key=value context (node=..., ticker=..., mode=...).
    This keeps logs grep-friendly and avoids embedding logic in the formatter.
    """

    def __init__(self, logger: logging.Logger, extra: Mapping[str, Any] | None = None):
        super().__init__(logger, dict(extra or {}))

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra") or {}
        merged = {**self.extra, **extra}

        if merged:
            ctx = " ".join(f"{k}={merged[k]}" for k in sorted(merged.keys()) if merged[k] is not None)
            msg = f"{ctx} | {msg}"

        # Ensure "extra" doesn’t leak into base logging unintentionally
        kwargs["extra"] = {}
        return msg, kwargs


@dataclass(frozen=True)
class LogCtx:
    """
    Convenience container for common fields.
    Keep this small and stable; don't store large blobs here.
    """
    node: str | None = None
    ticker: str | None = None
    mode: str | None = None
    run_id: str | None = None

    def as_extra(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "ticker": self.ticker,
            "mode": self.mode,
            "run_id": self.run_id,
        }


def with_ctx(logger: logging.Logger, ctx: LogCtx | Mapping[str, Any] | None = None) -> ContextLoggerAdapter:
    """
    Wrap a logger with ContextLoggerAdapter.
    """
    if ctx is None:
        return ContextLoggerAdapter(logger, {})
    if isinstance(ctx, LogCtx):
        return ContextLoggerAdapter(logger, ctx.as_extra())
    return ContextLoggerAdapter(logger, dict(ctx))


def is_trace_enabled(logger: logging.Logger) -> bool:
    """
    Lightweight check used in nodes to avoid building expensive debug strings.
    """
    return logger.isEnabledFor(logging.DEBUG)
