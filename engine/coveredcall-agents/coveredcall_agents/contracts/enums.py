"""
coveredcall_agents/contracts/enums.py

Purpose:
    Shared enums used across fundamentals, policy, and graph/state to avoid circular imports.
"""

from __future__ import annotations

from enum import Enum


class Stance(str, Enum):
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"


class CoveredCallBias(str, Enum):
    CAUTION = "CAUTION"
    INCOME = "INCOME"
    UPSIDE = "UPSIDE"


class TradeAction(str, Enum):
    SELL_CALL = "SELL_CALL"
    SELL_CALL_MORE_OTM = "SELL_CALL_MORE_OTM"
    HOLD = "HOLD"
    AVOID_CALLS = "AVOID_CALLS"
    CLOSE_OR_ROLL = "CLOSE_OR_ROLL"
