"""
CLI entrypoint for coveredcall-agents.
Runs the fundamentals pipeline for a ticker and prints either human-readable output or JSON.

Pretty output goes to stdout via oprint().
Diagnostics/trace/debug go to stderr via logging.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from coveredcall_agents.api.run_analysis import run_analysis
from coveredcall_agents.config.default_config import DEFAULT_CONFIG
from coveredcall_agents.fundamentals.mode import FundamentalsMode
from coveredcall_agents.graph.covered_call_graph import CoveredCallAgentsGraph
from coveredcall_agents.llm.client import (
    ENV_LLM_MODEL_IDENTIFIER,
    ENV_LLM_PROVIDER,
    ENV_LLM_TIMEOUT_SECONDS,
    ENV_LLM_TRACE_ENABLED,
    ENV_OLLAMA_BASE_URL,
)

from cli.logging_setup import setup_cli_logging


logger = logging.getLogger("coveredcall_agents.cli")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def oprint(*args, **kwargs) -> None:
    """
    User-facing output printer (stdout).
    Use this for --output=pretty so pipes/redirection work as expected.
    """
    try:
        print(*args, file=sys.stdout, flush=True, **kwargs)
    except BrokenPipeError:
        raise SystemExit(0)


def _deep_copy(obj: dict) -> dict:
    return json.loads(json.dumps(obj))


def _fmt_pct(x: float | None, ndigits: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x:.{ndigits}f}%"


def _fmt_float(x: float | None, ndigits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{ndigits}f}"


def _fmt_money(x: float | None) -> str:
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


def _print_section(title: str) -> None:
    oprint("")
    oprint(title)
    oprint("=" * len(title))


def _print_appendix(appendix: str | None) -> None:
    if not appendix:
        return
    _print_section("Diagnostics")
    oprint(str(appendix).strip())


def _print_pretty_fundamentals(report) -> None:
    snap = report.snapshot
    q = snap.quality

    stance = getattr(report.stance, "value", str(report.stance))
    bias = getattr(report.covered_call_bias, "value", str(report.covered_call_bias))

    oprint(f"{snap.ticker} Fundamentals")
    oprint("-" * (len(snap.ticker) + 13))
    oprint(f"Stance: {stance} | Bias: {bias} | Confidence: {report.confidence:.2f}")

    # Phase 2: surface policy action in pretty output
    action = getattr(report, "action", None)
    action_s = getattr(action, "value", str(action)) if action is not None else "—"
    oprint(f"Action: {action_s}")
    reason = getattr(report, "action_reason", None)
    if reason:
        oprint(f"Action reason: {reason}")

    oprint(f"As of: {q.as_of} | Provider stub: {q.is_stub}")
    oprint("")

    oprint("Snapshot")
    oprint("--------")
    oprint(f"Price:            {_fmt_float(snap.price, 2)}")
    oprint(f"Market cap:       {_fmt_money(snap.market_cap)}")
    oprint(f"Revenue YoY:      {_fmt_pct(snap.revenue_growth_yoy_pct)}")
    oprint(f"EPS YoY:          {_fmt_pct(snap.eps_growth_yoy_pct)}")
    oprint(f"Gross margin:     {_fmt_pct(snap.gross_margin_pct)}")
    oprint(f"Operating margin: {_fmt_pct(snap.operating_margin_pct)}")
    oprint(f"Debt-to-equity:   {_fmt_float(snap.debt_to_equity, 2)}")
    oprint("")

    oprint("Key points")
    oprint("----------")
    for i, s in enumerate(report.key_points, 1):
        oprint(f"{i}. {s}")
    oprint("")

    risks = list(report.risks or [])
    if q.missing_fields:
        risks.append(f"Missing fields: {', '.join(q.missing_fields)}")
    if q.warnings:
        risks.extend(q.warnings)

    if risks:
        oprint("Risks / cautions")
        oprint("--------------")
        for i, s in enumerate(risks, 1):
            oprint(f"{i}. {s}")
        oprint("")


def _apply_llm_cli_overrides_to_env(args: argparse.Namespace) -> None:
    """
    Apply CLI LLM overrides by setting environment variables.

    CoveredCallAgentsGraph builds the LLM client from env.
    This bridge keeps CLI dev flexibility without duplicating provider logic.

    Design:
        - CLI provides a dev default for Ollama base URL to match existing tests.
        - Library remains strict (no hidden defaults) via LLMRuntimeConfig.from_env().
    """
    if args.llm_provider:
        provider_raw = (args.llm_provider or "").strip().lower()

        # Map legacy CLI "none" to runtime "stub".
        if provider_raw == "none":
            os.environ[ENV_LLM_PROVIDER] = "stub"
        else:
            os.environ[ENV_LLM_PROVIDER] = provider_raw

        if args.llm_model:
            os.environ[ENV_LLM_MODEL_IDENTIFIER] = str(args.llm_model).strip()

        # Always set base URL for ollama (CLI default covers this).
        if provider_raw == "ollama":
            base_url = str(args.llm_base_url or DEFAULT_OLLAMA_BASE_URL).strip()
            os.environ[ENV_OLLAMA_BASE_URL] = base_url

        if args.llm_timeout_s is not None:
            os.environ[ENV_LLM_TIMEOUT_SECONDS] = str(float(args.llm_timeout_s))

    # Keep trace behavior consistent across providers.
    if args.trace or args.force_debate:
        os.environ[ENV_LLM_TRACE_ENABLED] = "1"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)

    p.add_argument("--output", choices=["pretty", "json"], default="pretty")
    p.add_argument("--json-indent", type=int, default=2)

    p.add_argument("--quiet", action="store_true")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--force-debate", action="store_true")

    p.add_argument("--fundamentals-provider", choices=["stub", "yfinance"], default=None)
    p.add_argument(
        "--fundamentals-mode",
        choices=[
            FundamentalsMode.DETERMINISTIC.value,
            FundamentalsMode.LLM.value,
            FundamentalsMode.AGENTIC.value,
            "llm_agentic",
        ],
    )

    # Include bedrock in CLI for dev flexibility (still uses env-driven provider registry).
    p.add_argument("--llm-provider", choices=["ollama", "bedrock", "mock", "none"], default=None)
    p.add_argument("--llm-model", default=None)

    # Dev-friendly default for ollama to keep tests/usage simple.
    p.add_argument("--llm-base-url", default=DEFAULT_OLLAMA_BASE_URL)

    p.add_argument("--llm-timeout-s", type=float, default=None)

    args = p.parse_args()

    setup_cli_logging(trace=args.trace)

    # Bridge CLI flags → env for LLM provider selection.
    _apply_llm_cli_overrides_to_env(args)

    cfg = _deep_copy(DEFAULT_CONFIG)

    # Apply CLI overrides (keep raw strings; graph normalizes via get_fundamentals_mode)
    if args.fundamentals_provider:
        cfg.setdefault("providers", {})["fundamentals"] = args.fundamentals_provider
    if args.fundamentals_mode:
        cfg.setdefault("fundamentals", {})["mode"] = args.fundamentals_mode

    cfg["trace"] = bool(args.trace or args.force_debate)
    if args.force_debate:
        cfg.setdefault("fundamentals", {})["force_debate"] = True

    # Keep these for backwards compatibility / visibility, but provider selection is env-driven.
    if args.llm_provider:
        cfg.setdefault("llm", {})["provider"] = args.llm_provider
    if args.llm_model:
        cfg.setdefault("llm", {})["model"] = args.llm_model
    if args.llm_base_url:
        cfg.setdefault("llm", {})["base_url"] = args.llm_base_url
    if args.llm_timeout_s is not None:
        cfg.setdefault("llm", {})["timeout_s"] = args.llm_timeout_s

    graph = CoveredCallAgentsGraph()
    try:
        out_state = graph.propagate(args.ticker, config=cfg)
    except ValueError as e:
        # Clean CLI failure (no traceback) for expected config/user errors.
        logger.error(str(e))
        raise SystemExit(2)

    if args.trace:
        logger.debug("TRACE")
        logger.debug("has snapshot=%s", out_state.fundamentals_snapshot is not None)
        logger.debug("has bull_case=%s", out_state.bull_case is not None)
        logger.debug("has bear_case=%s", out_state.bear_case is not None)
        logger.debug("has debate_summary=%s", out_state.debate_summary is not None)
        logger.debug("has report=%s", out_state.fundamentals_report is not None)

    report = out_state.fundamentals_report
    if report is None:
        raise RuntimeError("fundamentals_report is None (unexpected).")

    if args.output == "json":
        try:
            try:
                sys.stdout.reconfigure(write_through=True)
            except Exception:
                pass
            sys.stdout.write(json.dumps(out_state.model_dump(), indent=args.json_indent, default=str) + "\n")
        except BrokenPipeError:
            return
    else:
        _print_pretty_fundamentals(report)
        _print_appendix(getattr(report, "appendix", None))

    # Keep stdout pure in --output json mode.
    # Only show these banners in pretty mode.
    if not args.quiet and args.output == "pretty":
        logger.info("Fundamentals provider=%s", cfg.get("providers", {}).get("fundamentals"))
        logger.info("Fundamentals mode=%s", cfg.get("fundamentals", {}).get("mode"))

    if args.trace:
        nodes = getattr(out_state, "trace_nodes", None)
        if nodes:
            logger.debug("NODE TRACE: %s", " → ".join(nodes))

        events = getattr(out_state, "trace_events", None)
        if events:
            for line in events:
                logger.debug("TRACE EVENT: %s", line)


if __name__ == "__main__":
    main()
