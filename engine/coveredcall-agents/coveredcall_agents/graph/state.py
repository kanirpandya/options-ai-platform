"""
state.py

Purpose:
    Defines the shared GraphState and Pydantic models passed between
    LangGraph nodes.

Role in system:
    Serves as the single source of truth for data contracts between
    agents, including explain payloads and debate artifacts.

Notes:
    Any change here is a breaking change for multiple nodes and must
    be accompanied by regression tests.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, confloat, conlist, model_validator

from coveredcall_agents.agentic.agentic_contracts import AgenticResponse
from coveredcall_agents.fundamentals.mode import FundamentalsMode
from ..tools.registry import Tools

from coveredcall_agents.contracts.enums import Stance, CoveredCallBias, TradeAction

# ---------------------------
# Small constrained list types
# ---------------------------
ShortBullets = conlist(str, min_length=0, max_length=2)
ShortRisks = conlist(str, min_length=0, max_length=1)
ShortSummary = conlist(str, min_length=0, max_length=2)
ShortPoints = conlist(str, min_length=0, max_length=4)


# ---------------------------
# Enums
# ---------------------------
class Stance(str, Enum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


class CoveredCallBias(str, Enum):
    UPSIDE = "UPSIDE"
    INCOME = "INCOME"
    CAUTION = "CAUTION"


# ---------------------------
# Final fundamentals resolution
# ---------------------------
class FinalSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    AGENTIC = "agentic"


class FinalFundamentalsDecision(BaseModel):
    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: confloat(ge=0.0, le=1.0)
    source: FinalSource
    rationale: str = ""


# ---------------------------
# Snapshot + quality
# ---------------------------
class DataQuality(BaseModel):
    as_of: datetime
    is_stub: bool = True
    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FundamentalSnapshot(BaseModel):
    ticker: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    revenue_growth_yoy_pct: Optional[float] = None
    eps_growth_yoy_pct: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    quality: DataQuality


# ---------------------------
# Agent argument + debate
# ---------------------------
class AgentArgument(BaseModel):
    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: confloat(ge=0.0, le=1.0) = 0.6
    bullets: ShortBullets = Field(default_factory=list)
    risks: ShortRisks = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_output(cls, data):
        if not isinstance(data, dict):
            return data

        if "stance" not in data and "position" in data:
            data["stance"] = data.pop("position")
        if "covered_call_bias" not in data and "bias" in data:
            data["covered_call_bias"] = data.pop("bias")

        if isinstance(data.get("stance"), str):
            data["stance"] = data["stance"].strip().upper()

        bias = data.get("covered_call_bias")
        if isinstance(bias, str):
            bias_norm = bias.strip().upper()
            if "|" in bias_norm:
                parts = [p.strip() for p in bias_norm.split("|") if p.strip()]
                if "CAUTION" in parts:
                    bias_norm = "CAUTION"
                elif "UPSIDE" in parts:
                    bias_norm = "UPSIDE"
                elif "INCOME" in parts:
                    bias_norm = "INCOME"
            data["covered_call_bias"] = bias_norm

        data.setdefault("confidence", 0.6)
        data.setdefault("bullets", [])
        data.setdefault("risks", [])

        if not data["bullets"] and "reasons" in data and isinstance(data["reasons"], list):
            data["bullets"] = [str(r) for r in data["reasons"][:2]]
            data.pop("reasons", None)

        data["bullets"] = list(map(str, data["bullets"][:2]))
        data["risks"] = list(map(str, data["risks"][:1]))

        return data


class DebateSummary(BaseModel):
    bull: AgentArgument
    bear: AgentArgument
    synthesis: ShortSummary = Field(default_factory=list)
    disagreements: ShortSummary = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_schema_variants(cls, data):
        if not isinstance(data, dict):
            return data

        if "synthesis" in data or "disagreements" in data:
            return data

        syn: list[str] = []
        summary = data.get("summary")
        if isinstance(summary, str) and summary.strip():
            syn.append(summary.strip())

        key_points = data.get("key_points")
        if isinstance(key_points, list):
            syn.extend([str(x).strip() for x in key_points if str(x).strip()])

        data["synthesis"] = syn[:2] if syn else []
        data.setdefault("disagreements", [])

        return data


# ---------------------------
# Fundamentals view (det / llm / agentic)
# ---------------------------
class FundamentalsView(BaseModel):
    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ---------------------------
# Divergence report
# ---------------------------
DivergenceSeverity = Literal["ALIGNED", "MINOR", "MAJOR", "CRITICAL"]


class DivergenceReport(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    severity: DivergenceSeverity
    stance: Tuple[str, str]
    covered_call_bias: Tuple[str, str]
    confidence: Tuple[float, float]
    stance_divergence: float = Field(..., ge=0.0, le=1.0)
    bias_divergence: float = Field(..., ge=0.0, le=1.0)
    confidence_divergence: float = Field(..., ge=0.0, le=1.0)
    action_hint: str
    notes: Optional[str] = None


# ---------------------------
# Explain payload + report
# ---------------------------
class FundamentalsExplainPayload(BaseModel):
    det_fundamentals: Optional[FundamentalsView] = None
    llm_fundamentals: Optional[FundamentalsView] = None
    agentic_fundamentals: Optional[FundamentalsView] = None

    divergence_report: Optional[DivergenceReport] = None
    divergence_reasons: List[str] = Field(default_factory=list)

    bull_case: Optional[AgentArgument] = None
    bear_case: Optional[AgentArgument] = None
    debate_summary: Optional[DebateSummary] = None

    mode: Optional[str] = None
    trace_nodes: Annotated[list[str], operator.add] = Field(default_factory=list)

# ---------------------------
# Proposal + LLM payload
# ---------------------------
class FundamentalProposal(BaseModel):
    ticker: str
    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: ShortPoints = Field(default_factory=list)
    risks: ShortRisks = Field(default_factory=list)
    
class FundamentalReport(BaseModel):
    ticker: str
    stance: Stance
    covered_call_bias: CoveredCallBias
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: ShortPoints
    risks: List[str] = Field(default_factory=list)
    snapshot: FundamentalSnapshot
    appendix: Optional[str] = None
    explain: Optional[FundamentalsExplainPayload] = None
    action: TradeAction | None = None
    action_reason: str | None = None

# ---------------------------
# Graph state
# ---------------------------
class GraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ticker: str
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    config: Dict[str, Any]
    tools: Tools

    llm: Any = Field(default=None, exclude=True)

    fundamentals_snapshot: Optional[FundamentalSnapshot] = None
    fundamentals_report: Optional[FundamentalReport] = None

    action: TradeAction | None = None
    action_reason: str | None = None

    bull_case: Optional[AgentArgument] = None
    bear_case: Optional[AgentArgument] = None
    debate_summary: Optional[DebateSummary] = None

    divergence_report: Optional[DivergenceReport] = None
    det_fundamentals: Optional[FundamentalsView] = None
    llm_fundamentals: Optional[FundamentalsView] = None
    agentic_fundamentals: Optional[FundamentalsView] = None

    trace_nodes: Annotated[list[str], operator.add] = Field(default_factory=list)

    agentic_result: Optional[AgenticResponse] = None
    agentic_tool_history: List[Dict[str, Any]] = Field(default_factory=list)

    final_fundamentals: Optional[FinalFundamentalsDecision] = None
