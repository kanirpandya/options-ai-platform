from __future__ import annotations

import json
from typing import Any, Dict

from ..graph.state import FundamentalSnapshot

SYSTEM_PROMPT = """You are a Fundamental Analysis Agent for covered call strategy.
You MUST follow these rules:
- Use ONLY the provided snapshot numbers. Do not invent any numbers.
- Output MUST be valid JSON and MUST conform to the provided JSON Schema.
- Do NOT add any "data quality warning" unless missing_fields or warnings are non-empty.
- Keep key_points concise and actionable.
- risks should include data quality warnings and material negatives.
- stance must be one of: BULLISH, NEUTRAL, BEARISH
- covered_call_bias must be one of: UPSIDE, INCOME, CAUTION
- Treat operating_margin_pct > 20% as strong; do not list as a risk.
- Include one key point like: “Bias rationale:...
"""


def build_user_prompt(snapshot: FundamentalSnapshot, config: Dict[str, Any]) -> str:
    # Provide snapshot + thresholds (so the model is guided but not forced)
    return json.dumps(
        {
            "task": "Interpret fundamentals snapshot into a FundamentalReport for covered-call decision bias.",
            "thresholds": config.get("fundamentals", {}),
            "snapshot": snapshot.model_dump(),
        },
        indent=2,
        default=str,
    )
