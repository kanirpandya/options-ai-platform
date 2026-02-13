"""
Default configuration for coveredcall-agents.

This file acts as the system control plane:
- which providers to use
- heuristic thresholds
- future agent / LLM knobs

Agents should READ from this config but never mutate it.
"""

DEFAULT_CONFIG = {
    # ------------------------------------------------------------------
    # Data providers (swappable without changing agent logic)
    # ------------------------------------------------------------------
    "providers": {
        # "stub" | "yfinance" | "sec" (future)
        "fundamentals": "yfinance",
    },
    # ------------------------------------------------------------------
    # Fundamental analysis heuristics
    # These are intentionally simple and interpretable.
    # ------------------------------------------------------------------
    "fundamentals": {
        # Growth
        "min_growth_pct": 0.0,  # below this is considered weak
        "strong_growth_pct": 5.0,  # above this counts as a bullish signal
        # Profitability
        "min_oper_margin_pct": 5.0,  # below this is a bearish signal
        "strong_oper_margin_pct": 30.0,  # above this is a bullish signal
        # Balance sheet
        "max_debt_to_equity": 2.0,  # above this is considered risky
        # Confidence tuning (optional, future)
        # "missing_data_penalty": 0.1,
    },
    # ------------------------------------------------------------------
    # Reserved sections for future agents (keep empty for now)
    # ------------------------------------------------------------------
    "llm": {
        "provider": "ollama",  # ollama | none
        "model": "llama3.1:8b",
        "base_url": "http://localhost:11434",
        "timeout_s": 30.0,
    },
    "debate": {
        # "enabled": False,
        # "rounds": 1,
    },
    "risk": {
        # "max_position_pct": 0.10,
        # "avoid_earnings_days": 7,
    },
}
