DEFAULT_CONFIG = {
    "providers": {
        "fundamentals": "stub"  # change to "yfinance" to use real data
    },
    "fundamentals": {
        "min_growth_pct": 0.0,
        "strong_growth_pct": 5.0,
        "min_oper_margin_pct": 5.0,
        "strong_oper_margin_pct": 10.0,
        "max_debt_to_equity": 2.0,
        "mode": "llm",
        "force_debate": True,
        "policy": {
            "abstain_on_severity": ["MAJOR", "CRITICAL"],
            "abstain_if_stance_divergence_gte": 0.5,
            "abstain_if_score_gte": 0.55,
            "abstain_label": "ABSTAIN/REVIEW",
        },
    },
}
