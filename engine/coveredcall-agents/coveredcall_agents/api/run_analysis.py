"""
coveredcall_agents.api.run_analysis

Purpose:
    Programmatic entrypoint to run the covered-call fundamentals pipeline without CLI parsing.
    This function is the shared execution path for:
      - CLI (cli/main.py)
      - AWS backend worker (Fargate) (future)

Used By:
    - coveredcall_agents.cli.main (human/JSON output formatting)
    - options-ai-platform backend worker (job_runner)

Design Notes:
    - No stdout printing (callers decide how to present results).
    - No hard-coded environment values or defaults beyond what is passed in.
    - Raises ValueError for expected configuration/user errors (callers may render cleanly).
    - Avoid AWS dependencies here (engine-only module).

Author:
    Kanir Pandya

Created:
    2026-02-13
"""

from __future__ import annotations

from typing import Any, Mapping

from coveredcall_agents.graph.covered_call_graph import CoveredCallAgentsGraph


def run_analysis(*, ticker: str, config: Mapping[str, Any]) -> GraphState:
    """
    Run the covered-call analysis graph and return the resulting graph state.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL").
        config: Engine configuration mapping (caller-controlled), typically derived from DEFAULT_CONFIG
                with overrides applied.

    Returns:
        The final graph state (Pydantic model) containing fundamentals_snapshot/report/etc.

    Raises:
        ValueError: For expected user/config errors (e.g., invalid mode/provider config).
        RuntimeError: For unexpected internal invariants.
    """
    graph = CoveredCallAgentsGraph()
    out_state = graph.propagate(ticker, config=dict(config))
    return out_state
