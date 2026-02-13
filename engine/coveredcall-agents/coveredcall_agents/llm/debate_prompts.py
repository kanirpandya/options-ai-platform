from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------

BULL_SYSTEM = """
You are a disciplined equity fundamentals analyst.
You must argue the BULLISH case using financial fundamentals only.
You are conservative, factual, and concise.

Hard rules:
- Output ONLY valid JSON (no markdown, no prose).
- Use ONLY the keys defined by the contract.
- Enum strings must match exactly (case-sensitive).
- Do NOT include literal newlines inside strings (use \\n if needed).

Brevity rules:
- Each bullet and risk must be <= 110 characters.
- Avoid trailing clauses like "considering ..." — finish the sentence.
- Prefer short phrases over long sentences.
"""

BEAR_SYSTEM = """
You are a disciplined equity risk analyst.
You must argue the BEARISH case using financial fundamentals only.
You are skeptical, factual, and concise.

Hard rules:
- Output ONLY valid JSON (no markdown, no prose).
- Use ONLY the keys defined by the contract.
- Enum strings must match exactly (case-sensitive).
- Do NOT include literal newlines inside strings (use \\n if needed).

Brevity rules:
- Each bullet and risk must be <= 110 characters.
- Avoid trailing clauses like "considering ..." — finish the sentence.
- Prefer short phrases over long sentences.
"""

DEBATE_SYSTEM = """
You are a neutral investment committee chair.
You must synthesize the bull and bear arguments objectively.

Hard rules:
- Output ONLY valid JSON (no markdown, no prose).
- Use ONLY the keys defined by the contract.
- Do NOT include literal newlines inside strings (use \\n if needed).

The JSON object must contain exactly these top-level keys:
"bull", "bear", "synthesis", "disagreements".

Rules:
- Use double quotes for all keys and strings.
- Do NOT include trailing commas.
- Do NOT include markdown fences.
"""

PROPOSAL_SYSTEM = """
You are a senior portfolio strategist.

You MUST return ONLY valid JSON that conforms to the provided JSON schema.

Hard rules:
- Output ONLY a JSON object (no markdown, no prose).
- Use ONLY the keys defined by the schema. Do NOT invent new keys.
  (For example, do NOT output keys like "recommendation", "strike price", "expiration date".)
- Enum strings must match exactly (case-sensitive).
- Do NOT include literal newlines inside strings (use \\n if needed).

Brevity rules:
- Each key_point and risk must be <= 110 characters.
- Avoid trailing clauses like "considering ..." — finish the sentence.
- Prefer short phrases over long sentences.
"""

SNAPSHOT_COPY_RULE = """
Rules:
- When citing a metric, copy the value EXACTLY as shown in the SNAPSHOT block (same rounding/units).
- Do NOT introduce facts not present in SNAPSHOT.
"""

# ---------------------------------------------------------------------
# OUTPUT CONTRACTS (CRITICAL)
# ---------------------------------------------------------------------

AGENT_ARGUMENT_OUTPUT = """
Return ONLY valid JSON with EXACTLY these keys:

{
  "stance": "BULLISH",
  "covered_call_bias": "UPSIDE",
  "confidence": 0.65,
  "bullets": ["short bullet", "short bullet"],
  "risks": []
}

Rules:
- Use EXACT key names shown above (case-sensitive).
- stance MUST be exactly one of: BULLISH, NEUTRAL, BEARISH.
- covered_call_bias MUST be exactly one of: UPSIDE, INCOME, CAUTION.
- confidence MUST be a number between 0.0 and 1.0.
- bullets MUST contain 1–2 concise strings.
- risks MUST contain 0–1 short strings.
- Return JSON ONLY. No markdown. No commentary.
- Do NOT include any additional keys beyond those shown.
- Do NOT output placeholder strings like "BULLISH|NEUTRAL|BEARISH" or "UPSIDE|INCOME|CAUTION".
"""

DEBATE_OUTPUT = """
Return ONLY valid JSON with EXACTLY these keys:

{
  "bull": {
    "stance": "BULLISH",
    "covered_call_bias": "UPSIDE",
    "confidence": 0.65,
    "bullets": ["short bullet", "short bullet"],
    "risks": []
  },
  "bear": {
    "stance": "BEARISH",
    "covered_call_bias": "CAUTION",
    "confidence": 0.60,
    "bullets": ["short bullet", "short bullet"],
    "risks": ["short risk"]
  },
  "synthesis": ["concise synthesis bullet", "concise synthesis bullet"],
  "disagreements": ["key disagreement"]
}

Rules:
- bull and bear MUST each follow the AgentArgument format exactly.
- synthesis should contain 1–2 bullets.
- disagreements may be empty [].
- Return JSON ONLY.
- Do NOT include any additional keys beyond those shown.
"""

FINAL_REPORT_OUTPUT = """
Return ONLY valid JSON with EXACTLY these keys:

{
  "ticker": "AAPL",
  "stance": "NEUTRAL",
  "covered_call_bias": "INCOME",
  "confidence": 0.60,
  "key_points": [
    "one sentence with at least one SNAPSHOT value",
    "one sentence with at least one SNAPSHOT value",
    "one sentence with at least one SNAPSHOT value",
    "Trade posture: <STANCE> + confidence <X.XX> → <ACTION> (grounded by <METRIC>: <VALUE>)"
  ],
  "risks": []
}

Rules (STRICT):
- Return JSON ONLY. No markdown. No extra keys.
- stance MUST be exactly one of: BULLISH, NEUTRAL, BEARISH.
- covered_call_bias MUST be exactly one of: UPSIDE, INCOME, CAUTION.
- confidence MUST be 0.0–1.0.
- key_points MUST contain EXACTLY 4 items.
- Each key_point MUST be ONE sentence and <= 22 words.
- Every key_point MUST include at least one value copied EXACTLY from the SNAPSHOT block
  (examples: "7.9%", "31.6%", "46.9%", "1.52", "3.83T", "259.47").
- Do NOT include threshold symbols or comparisons in text (no >=, <=, >, <, "threshold").
- Do NOT describe price as OK/strong/weak.
- Do NOT mention volatility/volatile or overall market direction.
- Do NOT output placeholder strings like "BULLISH|NEUTRAL|BEARISH" or "UPSIDE|INCOME|CAUTION".

Trade posture line (STRICT):
- The LAST key_point MUST start with "Trade posture:".
- It MUST use <STANCE> (BULLISH/NEUTRAL/BEARISH), NOT the bias.
- It MUST use ONE allowed action phrase exactly:
  - "sell closer-to-ATM calls to prioritize premium"
  - "sell moderately OTM calls to balance income and upside"
  - "sell far OTM calls or consider no-trade"
- The "(grounded by ...)" portion MUST reference a real SNAPSHOT metric, e.g. "Revenue growth YoY: 7.9%".

Risks (STRICT):
- risks may be [] or contain EXACTLY 1 short item.
- If present, the risk MUST cite a SNAPSHOT value or a DataQuality warning string.
"""

# ---------------------------------------------------------------------
# USER PROMPTS
# ---------------------------------------------------------------------


def _fmt_pct(x: float | None, ndigits: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x:.{ndigits}f}%"


def _fmt_float(x: float | None, ndigits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{ndigits}f}"


def _fmt_mcap(x: float | None) -> str:
    if x is None:
        return "—"
    absx = abs(x)
    if absx >= 1e12:
        return f"{x / 1e12:.2f}T"
    if absx >= 1e9:
        return f"{x / 1e9:.2f}B"
    if absx >= 1e6:
        return f"{x / 1e6:.2f}M"
    if absx >= 1e3:
        return f"{x / 1e3:.2f}K"
    return f"{x:.2f}"


def snapshot_block(snapshot) -> str:
    """Compact snapshot text with stable rounding to keep token count low."""
    return (
        f"Ticker: {snapshot.ticker}\n"
        f"Price: {_fmt_float(snapshot.price, 2)}\n"
        f"Market cap: {_fmt_mcap(snapshot.market_cap)}\n"
        f"Revenue growth YoY: {_fmt_pct(snapshot.revenue_growth_yoy_pct, 1)}\n"
        f"EPS growth YoY: {_fmt_pct(snapshot.eps_growth_yoy_pct, 1)}\n"
        f"Gross margin: {_fmt_pct(snapshot.gross_margin_pct, 1)}\n"
        f"Operating margin: {_fmt_pct(snapshot.operating_margin_pct, 1)}\n"
        f"Debt to equity: {_fmt_float(snapshot.debt_to_equity, 2)}\n"
    )


def bear_user(snapshot, config: Dict[str, Any]) -> str:
    return f"""
You are arguing the BEARISH case for this stock based on fundamentals.

SNAPSHOT:
{snapshot_block(snapshot)}

Focus on:
- Leverage or balance-sheet risk
- Margin sustainability
- Growth durability
- Valuation or macro sensitivity

{SNAPSHOT_COPY_RULE}
{AGENT_ARGUMENT_OUTPUT}
"""


def bull_user(snapshot, config: Dict[str, Any]) -> str:
    return f"""
You are arguing the BULLISH case for this stock based on fundamentals.

SNAPSHOT:
{snapshot_block(snapshot)}

Focus on:
- Growth strength
- Profitability
- Balance-sheet resilience
- Competitive positioning

{SNAPSHOT_COPY_RULE}
{AGENT_ARGUMENT_OUTPUT}
"""


def debate_user(snapshot, bull: Dict[str, Any], bear: Dict[str, Any]) -> str:
    return f"""
You are synthesizing a bull vs bear debate.

SNAPSHOT:
{snapshot_block(snapshot)}

BULL ARGUMENT (JSON):
{bull}

BEAR ARGUMENT (JSON):
{bear}

Your task:
- Objectively summarize areas of agreement and disagreement
- Do NOT introduce new facts

{SNAPSHOT_COPY_RULE}
{DEBATE_OUTPUT}
"""


PROPOSAL_USER_CONTRACT = """
Return ONLY JSON and follow FINAL_REPORT_OUTPUT exactly.

Use ONLY these keys (exact spelling):
- ticker
- stance
- covered_call_bias
- confidence
- key_points
- risks

Do NOT output keys like: position, bullets, recommendation, strike price, expiration date.

Array limits:
- key_points: EXACTLY 4 strings
- risks: [] or EXACTLY 1 string
"""


def proposal_user(snapshot, debate_summary: Dict[str, Any], config: Dict[str, Any]) -> str:
    # Pull deterministic thresholds (fallback defaults if not present)
    fcfg = config.get("fundamentals", {}) or {}
    strong_growth = float(fcfg.get("strong_growth_pct", 5.0))
    strong_margin = float(fcfg.get("strong_oper_margin_pct", 10.0))
    min_margin = float(fcfg.get("min_oper_margin_pct", 5.0))
    max_d2e = float(fcfg.get("max_debt_to_equity", 2.0))
    min_growth = float(fcfg.get("min_growth_pct", 0.0))

    # -----------------------------------------------------------------
    # REQUIRED LABELS (computed here so the LLM can't invent adjectives)
    # -----------------------------------------------------------------
    rev = getattr(snapshot, "revenue_growth_yoy_pct", None)
    opm = getattr(snapshot, "operating_margin_pct", None)
    gm = getattr(snapshot, "gross_margin_pct", None)
    d2e = getattr(snapshot, "debt_to_equity", None)

    # Revenue growth label
    if rev is None:
        rev_label = "—"
    elif rev >= strong_growth:
        rev_label = "strong"
    elif rev >= min_growth:
        rev_label = "moderate"
    else:
        rev_label = "weak"

    # Operating margin label
    if opm is None:
        opm_label = "—"
    elif opm >= strong_margin:
        opm_label = "strong"
    elif opm >= min_margin:
        opm_label = "OK"
    else:
        opm_label = "weak"

    # Gross margin label
    if gm is None:
        gm_label = "—"
    elif gm >= 40.0:
        gm_label = "strong"
    elif gm >= 30.0:
        gm_label = "OK"
    else:
        gm_label = "weak"

    # Debt-to-equity label
    if d2e is None:
        d2e_label = "—"
    elif d2e > max_d2e:
        d2e_label = "elevated"
    elif d2e > 1.0:
        d2e_label = "moderate"
    else:
        d2e_label = "low"

    return f"""
You are producing the FINAL fundamentals-based recommendation.

SNAPSHOT (ground truth numbers; do not invent anything):
{snapshot_block(snapshot)}

DEBATE SUMMARY (JSON):
{debate_summary}

REQUIRED LABELS (MUST use these exact words if you describe the metric):
- Revenue growth is {rev_label}.
- Operating margin is {opm_label}.
- Gross margin is {gm_label}.
- Debt-to-equity is {d2e_label}.
Hard rule: You MUST NOT use any other adjective for these metrics.
Example allowed: "Operating margin is {opm_label}: 31.6%."
Example forbidden: "Moderate operating margin: 31.6%." (must use OK)

INTERPRETATION THRESHOLDS (use internally; do NOT print comparisons):
- Revenue growth STRONG: at least {strong_growth:.1f}%.
- Revenue growth MODERATE: at least {min_growth:.1f}% but below {strong_growth:.1f}%.
- Revenue growth WEAK: below {min_growth:.1f}%.
- Operating margin STRONG: at least {strong_margin:.1f}%.
- Operating margin OK: at least {min_margin:.1f}% but below {strong_margin:.1f}%.
- Operating margin WEAK: below {min_margin:.1f}%.
- Gross margin STRONG: at least 40.0%.
- Gross margin OK: at least 30.0% but below 40.0%.
- Gross margin WEAK: below 30.0%.
- Debt-to-equity ELEVATED: above {max_d2e:.2f}.
- Debt-to-equity MODERATE: above 1.00 and at most {max_d2e:.2f}.
- Debt-to-equity LOW: 1.00 or lower.

ROUNDING RULES (apply in text):
- Percentages: 1 decimal place (e.g., 31.6%)
- Debt-to-equity: 2 decimals (e.g., 1.52)
- Price: 2 decimals
- Market cap: 2 decimals in trillions if shown (e.g., 3.86T)

COVERED-CALL BIAS MAPPING (choose one):
- UPSIDE: Fundamentals are bullish → prefer higher strike / more OTM calls.
- INCOME: Fundamentals neutral → prefer closer strikes to harvest premium.
- CAUTION: Fundamentals bearish → consider no-trade or very conservative calls.

OUTPUT QUALITY RULES:
- When citing a metric, you MUST copy the value exactly as shown in the SNAPSHOT block (same rounding/units).
- Every key_point and risk MUST cite at least one metric value from SNAPSHOT in the same sentence.
- key_points MUST contain EXACTLY 4 items.
- risks must be [] or EXACTLY 1 item.
- The LAST key_point must start with: "Trade posture:"
- Use ONE allowed action phrase exactly:
  - "sell closer-to-ATM calls to prioritize premium"
  - "sell moderately OTM calls to balance income and upside"
  - "sell far OTM calls or consider no-trade"
- Use this exact structure for the final key point:
  "Trade posture: <STANCE> + confidence <X.XX> → <ACTION> (grounded by <METRIC>=<VALUE>)"

{PROPOSAL_USER_CONTRACT}
{FINAL_REPORT_OUTPUT}
"""
