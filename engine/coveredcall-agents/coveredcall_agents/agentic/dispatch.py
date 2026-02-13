# coveredcall_agents/agentic/dispatch.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from .agentic_contracts import AgenticToolName, ToolResult
from .normalization import coerce_args, normalize_tool_name

ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class DispatchConfig:
    include_allowed_tools_in_error: bool = True


def dispatch_agentic_tool(
    *,
    tool_registry: Mapping[AgenticToolName, ToolFn],
    tool: Any,
    args: Any,
    config: Optional[DispatchConfig] = None,
) -> ToolResult:
    cfg = config or DispatchConfig()

    t = normalize_tool_name(tool)
    a = coerce_args(args)

    if t is None:
        allowed = [x.value for x in AgenticToolName]
        msg = f"Unknown tool '{tool}'."
        if cfg.include_allowed_tools_in_error:
            msg += f" Allowed tools: {allowed}"
        return ToolResult(tool=None, ok=False, result={}, error=msg)

    fn = tool_registry.get(t)
    if fn is None:
        return ToolResult(
            tool=t.value, ok=False, result={}, error=f"Tool '{t.value}' not registered"
        )

    try:
        out = fn(a)
        if out is None:
            out = {}
        if not isinstance(out, dict):
            out = {"value": out}
        return ToolResult(tool=t.value, ok=True, result=out, error=None)
    except Exception as e:
        return ToolResult(tool=t.value, ok=False, result={}, error=f"{type(e).__name__}: {e}")
