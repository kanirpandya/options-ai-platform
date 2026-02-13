# coveredcall_agents/graph/node_ids.py
# Purpose: Centralize LangGraph node IDs to avoid scattered string literals and typos.

from __future__ import annotations

from enum import Enum


class NodeId(str, Enum):
    FUNDAMENTAL = "fundamental"
    DET = "det"
    LLM = "llm"
    AGENTIC = "agentic"
    DIVERGENCE = "divergence"
    FANOUT_LLM = "fanout_llm"
    BULL = "bull"
    BEAR = "bear"
    DEBATE = "debate"
    FUND_RESOLVE = "fund_resolve"
    PROPOSAL = "proposal"
