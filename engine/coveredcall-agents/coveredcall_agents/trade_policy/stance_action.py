"""
coveredcall_agents/trade_policy/stance_action.py

Purpose:
    Central stance→action trade policy (single source of truth). Deterministic + unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass

from coveredcall_agents.contracts.enums import Stance, CoveredCallBias, TradeAction


@dataclass(frozen=True)
class TradePolicyDecision:
    action: TradeAction
    reason: str


def decide_trade_action(
    *,
    stance: Stance,
    bias: CoveredCallBias,
    confidence: float,
    min_confidence: float = 0.55,
) -> TradePolicyDecision:
    """
    Central decision rule for stance→action.

    Notes:
    - Keep this conservative & deterministic.
    - Confidence gate prevents over-trading when model is unsure.
    """
    if confidence < min_confidence:
        return TradePolicyDecision(
            action=TradeAction.HOLD,
            reason=f"Confidence {confidence:.2f} < {min_confidence:.2f}; avoid acting on weak signal.",
        )

    # Primary rule: stance drives risk posture; bias refines execution.
    if stance == Stance.BULLISH:
        if bias == CoveredCallBias.UPSIDE:
            return TradePolicyDecision(
                action=TradeAction.AVOID_CALLS,
                reason="Bullish + UPSIDE: avoid capping upside with covered calls.",
            )
        if bias == CoveredCallBias.INCOME:
            return TradePolicyDecision(
                action=TradeAction.SELL_CALL_MORE_OTM,
                reason="Bullish + INCOME: if writing calls, prefer more OTM strikes to preserve upside.",
            )
        # CAUTION or other
        return TradePolicyDecision(
            action=TradeAction.SELL_CALL_MORE_OTM,
            reason="Bullish with caution: write calls only if needed; prefer more OTM.",
        )

    if stance == Stance.NEUTRAL:
        if bias == CoveredCallBias.INCOME:
            return TradePolicyDecision(
                action=TradeAction.SELL_CALL,
                reason="Neutral + INCOME: baseline covered call posture.",
            )
        if bias == CoveredCallBias.UPSIDE:
            return TradePolicyDecision(
                action=TradeAction.HOLD,
                reason="Neutral + UPSIDE: wait rather than cap upside without strong conviction.",
            )
        return TradePolicyDecision(
            action=TradeAction.HOLD,
            reason="Neutral + CAUTION: default to waiting.",
        )

    # BEARISH
    if stance == Stance.BEARISH:
        if bias == CoveredCallBias.INCOME:
            return TradePolicyDecision(
                action=TradeAction.SELL_CALL,
                reason="Bearish + INCOME: covered calls can reduce basis; prefer closer-to-money if desired (execution layer).",
            )
        if bias == CoveredCallBias.CAUTION:
            return TradePolicyDecision(
                action=TradeAction.CLOSE_OR_ROLL,
                reason="Bearish + CAUTION: reduce risk; if short calls exist, consider roll/close; otherwise avoid new calls.",
            )
        return TradePolicyDecision(
            action=TradeAction.AVOID_CALLS,
            reason="Bearish + UPSIDE mismatch: avoid new calls; signal conflict.",
        )

    # Fallback: never crash if new enum values appear
    return TradePolicyDecision(
        action=TradeAction.HOLD,
        reason=f"Unhandled stance/bias combination (stance={stance}, bias={bias}); default HOLD.",
    )
