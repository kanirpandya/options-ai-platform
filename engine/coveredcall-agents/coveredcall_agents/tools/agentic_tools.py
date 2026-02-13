from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from coveredcall_agents.agentic.agentic_contracts import (
    AgenticToolName,
    ToolCall,
    ToolResult,
)
from coveredcall_agents.agentic.dispatch import dispatch_agentic_tool as _dispatch

ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _dump(x: Any) -> Any:
    """Make objects JSON-serializable for LLM consumption."""
    if hasattr(x, "model_dump"):
        return x.model_dump()
    return x


# ---------- Tool implementations (READ-ONLY) ----------


def get_snapshot(state) -> Dict[str, Any]:
    """Return the grounded fundamentals snapshot."""
    snap = getattr(state, "fundamentals_snapshot", None)
    if snap is None:
        return {"has_snapshot": False}

    return {
        "has_snapshot": True,
        "snapshot": _dump(snap),
    }


def get_top_candidates(state, n: int = 5) -> Dict[str, Any]:
    """Return top-N option candidates from scoring (if present)."""
    scoring = getattr(state, "scoring", None)
    candidates = getattr(scoring, "candidates", None) if scoring else None

    if not candidates:
        return {"has_scoring": False, "candidates": []}

    n = max(1, min(int(n), 10))
    return {
        "has_scoring": True,
        "candidates": [_dump(c) for c in candidates[:n]],
    }


def explain_filter_rejections(state) -> Dict[str, Any]:
    """Return filter rejection counts for explanation/debugging."""
    scoring = getattr(state, "scoring", None)
    fs = getattr(scoring, "filter_stats", None) if scoring else None
    rejected = getattr(fs, "rejected_counts", None) if fs else None

    return {
        "has_filter_stats": bool(rejected),
        "rejected_counts": dict(rejected or {}),
    }


# ---------- Registry (WHITELIST) ----------


def _tool_registry(state) -> Mapping[AgenticToolName, ToolFn]:
    """
    Wrap stateful tools into a pure (args)->dict callable shape.
    """

    def _snapshot(_args: Dict[str, Any]) -> Dict[str, Any]:
        return get_snapshot(state)

    def _top_candidates(args: Dict[str, Any]) -> Dict[str, Any]:
        n = int((args or {}).get("n", 5))
        return get_top_candidates(state, n=n)

    def _rejections(_args: Dict[str, Any]) -> Dict[str, Any]:
        return explain_filter_rejections(state)

    return {
        AgenticToolName.GET_SNAPSHOT: _snapshot,
        AgenticToolName.GET_TOP_CANDIDATES: _top_candidates,
        AgenticToolName.EXPLAIN_FILTER_REJECTIONS: _rejections,
    }


# ---------- Dispatcher (NORMALIZED) ----------


def dispatch_agentic_tool(state, call: ToolCall) -> ToolResult:
    """
    Execute exactly one allowed tool call.
    This is the safety gate for the agentic loop.

    - Accepts call.tool as a string (LLM may use aliases)
    - Normalizes tool name + args
    - Never raises; returns ToolResult(ok=False) on error
    """
    return _dispatch(
        tool_registry=_tool_registry(state),
        tool=call.tool,
        args=call.args,
    )
