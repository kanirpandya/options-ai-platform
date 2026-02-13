# Purpose: Unit tests for stance→action trade policy mapping (single source of truth).

import pytest

from coveredcall_agents.trade_policy import TradeAction, decide_trade_action
from coveredcall_agents.graph.state import Stance, CoveredCallBias  # adjust import if needed


@pytest.mark.parametrize(
    "stance,bias,confidence,expected",
    [
        # confidence gate
        (Stance.BULLISH, CoveredCallBias.UPSIDE, 0.40, TradeAction.HOLD),
        (Stance.NEUTRAL, CoveredCallBias.INCOME, 0.54, TradeAction.HOLD),

        # bullish
        (Stance.BULLISH, CoveredCallBias.UPSIDE, 0.80, TradeAction.AVOID_CALLS),
        (Stance.BULLISH, CoveredCallBias.INCOME, 0.80, TradeAction.SELL_CALL_MORE_OTM),
        (Stance.BULLISH, CoveredCallBias.CAUTION, 0.80, TradeAction.SELL_CALL_MORE_OTM),

        # neutral
        (Stance.NEUTRAL, CoveredCallBias.INCOME, 0.80, TradeAction.SELL_CALL),
        (Stance.NEUTRAL, CoveredCallBias.UPSIDE, 0.80, TradeAction.HOLD),
        (Stance.NEUTRAL, CoveredCallBias.CAUTION, 0.80, TradeAction.HOLD),

        # bearish
        (Stance.BEARISH, CoveredCallBias.INCOME, 0.80, TradeAction.SELL_CALL),
        (Stance.BEARISH, CoveredCallBias.CAUTION, 0.80, TradeAction.CLOSE_OR_ROLL),
        (Stance.BEARISH, CoveredCallBias.UPSIDE, 0.80, TradeAction.AVOID_CALLS),
    ],
)
def test_trade_policy_mapping(stance, bias, confidence, expected):
    d = decide_trade_action(stance=stance, bias=bias, confidence=confidence)
    assert d.action == expected
    assert isinstance(d.reason, str) and d.reason


def test_trade_policy_min_conf_override():
    d = decide_trade_action(
        stance=Stance.NEUTRAL,
        bias=CoveredCallBias.INCOME,
        confidence=0.60,
        min_confidence=0.65,
    )
    assert d.action == TradeAction.HOLD
