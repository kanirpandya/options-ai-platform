from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .agentic_contracts import AgenticToolName

# Canonical aliases: map messy/alternate names -> strict enum
_TOOL_ALIASES: Dict[str, AgenticToolName] = {
    # Snapshot
    "get_snapshot": AgenticToolName.GET_SNAPSHOT,
    "snapshot": AgenticToolName.GET_SNAPSHOT,
    "get_quote": AgenticToolName.GET_SNAPSHOT,
    "quote": AgenticToolName.GET_SNAPSHOT,
    "price_snapshot": AgenticToolName.GET_SNAPSHOT,
    # Candidates
    "get_top_candidates": AgenticToolName.GET_TOP_CANDIDATES,
    "top_candidates": AgenticToolName.GET_TOP_CANDIDATES,
    "candidates": AgenticToolName.GET_TOP_CANDIDATES,
    "rank_candidates": AgenticToolName.GET_TOP_CANDIDATES,
    "select_candidates": AgenticToolName.GET_TOP_CANDIDATES,
    # Rejections
    "explain_filter_rejections": AgenticToolName.EXPLAIN_FILTER_REJECTIONS,
    "filter_rejections": AgenticToolName.EXPLAIN_FILTER_REJECTIONS,
    "rejections": AgenticToolName.EXPLAIN_FILTER_REJECTIONS,
    "explain_rejections": AgenticToolName.EXPLAIN_FILTER_REJECTIONS,
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify_tool_name(s: str) -> str:
    s = s.strip().lower()
    s = _NON_ALNUM.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def normalize_tool_name(raw: Any) -> Optional[AgenticToolName]:
    """
    Convert raw tool name into a strict AgenticToolName enum.
    Returns None if unknown/unparseable.
    """
    if raw is None:
        return None

    if isinstance(raw, AgenticToolName):
        return raw

    s = str(raw).strip()
    if not s:
        return None

    slug = _slugify_tool_name(s)

    # Direct match to enum values
    for t in AgenticToolName:
        if slug == t.value:
            return t

    # Alias match
    return _TOOL_ALIASES.get(slug)


def coerce_args(raw: Any) -> Dict[str, Any]:
    """
    Force args into a dict. Handles dict | json-string | None.
    Also normalizes common key variants (ticker/symbol).
    """
    if raw is None:
        return {}

    if isinstance(raw, dict):
        d = dict(raw)
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        d = dict(parsed)
    else:
        return {}

    # Normalize common ticker key variants
    if "ticker" not in d:
        for k in ("symbol", "underlying", "asset", "stock"):
            if k in d:
                d["ticker"] = d.pop(k)
                break

    return d
