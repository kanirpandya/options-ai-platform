from __future__ import annotations

from typing import Type

from pydantic import BaseModel


class MockLLMClient:
    def generate_json(
        self, system: str, user: str, schema: dict, model: Type[BaseModel]
    ) -> BaseModel:
        name = model.__name__

        if name == "AgentArgument":
            # minimal valid payload for your schema
            payload = {
                "stance": "BULLISH",
                "covered_call_bias": "UPSIDE",
                "confidence": 0.7,
                "bullets": ["Mock argument bullet 1", "Mock argument bullet 2"],
                "risks": [],
            }
            return model.model_validate(payload)

        if name == "DebateSummary":
            payload = {
                "bull": {
                    "stance": "BULLISH",
                    "covered_call_bias": "UPSIDE",
                    "confidence": 0.7,
                    "bullets": ["Bull mock"],
                    "risks": [],
                },
                "bear": {
                    "stance": "BEARISH",
                    "covered_call_bias": "CAUTION",
                    "confidence": 0.6,
                    "bullets": ["Bear mock"],
                    "risks": ["Mock risk"],
                },
                "synthesis": ["Mock synthesis point"],
                "disagreements": ["Mock disagreement"],
            }
            return model.model_validate(payload)

        if name == "FundamentalReport":
            payload = {
                "ticker": "AAPL",
                "stance": "NEUTRAL",
                "covered_call_bias": "INCOME",
                "confidence": 0.65,
                "key_points": ["Mock key point"],
                "risks": [],
                # snapshot will be overwritten/grounded in proposal_node anyway,
                # but we must supply it to satisfy schema validation:
                "snapshot": {
                    "ticker": "AAPL",
                    "price": None,
                    "market_cap": None,
                    "revenue_growth_yoy_pct": None,
                    "eps_growth_yoy_pct": None,
                    "gross_margin_pct": None,
                    "operating_margin_pct": None,
                    "debt_to_equity": None,
                    "quality": {
                        "as_of": "2026-01-01T00:00:00Z",
                        "is_stub": True,
                        "missing_fields": [],
                        "warnings": [],
                    },
                },
            }
            return model.model_validate(payload)

        if name == "LLMFundamentalsPayload":
            payload = {
                "stance": "BEARISH",
                "covered_call_bias": "CAUTION",
                "confidence": 0.95,
                "bullets": ["Mock bearish view"],
                "risks": ["Mock risk"],
            }
            return model.model_validate(payload)

        if name == "FundamentalProposal":
            payload = {
                "ticker": "AAPL",
                "stance": "NEUTRAL",
                "covered_call_bias": "INCOME",
                "confidence": 0.55,
                "key_points": [
                    "Mock proposal point 1",
                    "Mock proposal point 2",
                    "Mock proposal point 3",
                    "Trade posture: INCOME + confidence 0.55 → consider covered calls at moderate strikes.",
                ],
                "risks": [],
            }
            return model.model_validate(payload)

        raise ValueError(f"MockLLMClient: unsupported model {name}")

    def generate_text(self, *, system: str, user: str) -> str:
        return "MOCK_TEXT"
