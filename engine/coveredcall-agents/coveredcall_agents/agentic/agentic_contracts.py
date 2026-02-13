from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AgenticAction(str, Enum):
    CALL_TOOL = "CALL_TOOL"
    PROPOSE = "PROPOSE"
    ABSTAIN = "ABSTAIN"


class AgenticToolName(str, Enum):
    GET_SNAPSHOT = "get_snapshot"
    GET_TOP_CANDIDATES = "get_top_candidates"
    EXPLAIN_FILTER_REJECTIONS = "explain_filter_rejections"


class ToolCall(BaseModel):
    # Keep as str to avoid validation failures on aliases like "snapshot" / "get-snapshot".
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: Optional[str] = None
    ok: bool = True
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


def extract_first_json(text: str) -> str:
    """
    Robust-ish extraction: find first {...} block and return it.
    """
    s = (text or "").strip()
    start = s.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    raise ValueError("Incomplete JSON object")


def _coerce_str_list(v: Any, *, item_key: str) -> List[str]:
    """
    Accept common LLM drift shapes:
      - ["a","b"]
      - [{"bullet":"a"},{"bullet":"b"}]
      - [{"risk":"x"}]
      - [{"text":"a"}] (fallback if only one string-like field exists)
      - "a"
      - None
    """
    if v is None:
        return []
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    if isinstance(v, list):
        out: List[str] = []
        for it in v:
            if it is None:
                continue
            if isinstance(it, str):
                s = it.strip()
                if s:
                    out.append(s)
                continue
            if isinstance(it, dict):
                preferred = it.get(item_key)
                if isinstance(preferred, str) and preferred.strip():
                    out.append(preferred.strip())
                    continue
                # fallback: if dict has exactly one string value, take it
                str_vals = [vv.strip() for vv in it.values() if isinstance(vv, str) and vv.strip()]
                if len(str_vals) == 1:
                    out.append(str_vals[0])
                    continue
            # last resort: stringify
            out.append(str(it))
        return out
    return [str(v)]


class AgenticResponse(BaseModel):
    action: AgenticAction

    # If action == CALL_TOOL
    tool_call: Optional[ToolCall] = None

    # If action in {PROPOSE, ABSTAIN}
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Optional (lets us evolve toward Proposal/Bull/Bear later)
    stance: Optional[str] = None  # "BULLISH" | "NEUTRAL" | "BEARISH"
    covered_call_bias: Optional[str] = None  # "INCOME" | "UPSIDE" | "CAUTION"

    bullets: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

    @field_validator("bullets", mode="before")
    @classmethod
    def _bullets_before(cls, v: Any) -> List[str]:
        return _coerce_str_list(v, item_key="bullet")[:4]

    @field_validator("risks", mode="before")
    @classmethod
    def _risks_before(cls, v: Any) -> List[str]:
        return _coerce_str_list(v, item_key="risk")[:4]
