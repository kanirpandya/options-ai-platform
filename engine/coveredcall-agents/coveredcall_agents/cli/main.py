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
import sys

from coveredcall_agents.api.run_analysis import run_analysis
from coveredcall_agents.config.default_config import DEFAULT_CONFIG
from coveredcall_agents.fundamentals.mode import FundamentalsMode

from coveredcall_agents.cli.logging_setup import setup_cli_logging


logger = logging.getLogger("coveredcall_agents.cli")


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


def _maybe_dump(obj):
    """
    Convert Pydantic-ish objects to plain dict when possible.

    Keeps the CLI JSON contract stable without coupling this module to
    specific internal model types.
    """
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def _get_any(out_state, *keys):
    """
    Best-effort accessor for either dict-like out_state or object-like (GraphState) out_state.
    Returns the first non-None value among keys.
    """
    for k in keys:
        if out_state is None:
            continue
        if isinstance(out_state, dict) and k in out_state and out_state[k] is not None:
            return out_state[k]
        if hasattr(out_state, k):
            v = getattr(out_state, k)
            if v is not None:
                return v
    return None


def _build_explain(out_state, cfg: dict) -> dict:
    """
    Build the stable JSON 'explain' contract expected by CLI regression tests.

    Keys required by tests:
      - det_fundamentals
      - llm_fundamentals
      - divergence_report
      - divergence_reasons
      - mode
      - trace_nodes

    Plus (when present / force-debate):
      - bull_case, bear_case, debate_summary
    """
    det = _maybe_dump(_get_any(out_state, "det_fundamentals", "deterministic_fundamentals"))
    llm = _maybe_dump(_get_any(out_state, "llm_fundamentals", "final_fundamentals"))
    div = _maybe_dump(_get_any(out_state, "divergence_report"))
    div_reasons = _get_any(out_state, "divergence_reasons") or []
    trace_nodes = _get_any(out_state, "trace_nodes") or []

    # Debate artifacts (may be None unless force-debate or severity gating triggers)
    bull_case = _maybe_dump(_get_any(out_state, "bull_case"))
    bear_case = _maybe_dump(_get_any(out_state, "bear_case"))
    debate_summary = _maybe_dump(_get_any(out_state, "debate_summary"))

    # Prefer config fundamentals.mode, but fall back to out_state if needed
    mode = (cfg.get("fundamentals", {}) or {}).get("mode") or _get_any(out_state, "fundamentals_mode", "mode")

    return {
        "det_fundamentals": det,
        "llm_fundamentals": llm,
        "divergence_report": div,
        "divergence_reasons": list(div_reasons) if isinstance(div_reasons, (list, tuple)) else div_reasons,
        "mode": mode,
        "trace_nodes": list(trace_nodes) if isinstance(trace_nodes, (list, tuple)) else trace_nodes,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "debate_summary": debate_summary,
    }


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

    p.add_argument("--llm-provider", choices=["ollama", "mock", "none"], default=None)
    p.add_argument("--llm-model", default=None)
    p.add_argument("--llm-base-url", default=None)
    p.add_argument("--llm-timeout-s", type=float, default=None)

    args = p.parse_args()

    # Note: quiet is handled by logging_setup module (stderr only).
    setup_cli_logging(trace=args.trace, quiet=args.quiet)

    cfg = _deep_copy(DEFAULT_CONFIG)

    # Apply CLI overrides (keep raw strings; graph normalizes via get_fundamentals_mode)
    if args.fundamentals_provider:
        cfg.setdefault("providers", {})["fundamentals"] = args.fundamentals_provider
    if args.fundamentals_mode:
        cfg.setdefault("fundamentals", {})["mode"] = args.fundamentals_mode

    cfg["trace"] = bool(args.trace or args.force_debate)
    if args.force_debate:
        cfg.setdefault("fundamentals", {})["force_debate"] = True

    # LLM settings live under config["llm"]
    if args.llm_provider:
        cfg.setdefault("llm", {})["provider"] = args.llm_provider
    if args.llm_model:
        cfg.setdefault("llm", {})["model"] = args.llm_model
    if args.llm_base_url:
        cfg.setdefault("llm", {})["base_url"] = args.llm_base_url
    if args.llm_timeout_s is not None:
        cfg.setdefault("llm", {})["timeout_s"] = args.llm_timeout_s

    try:
        out_state = run_analysis(ticker=args.ticker, config=cfg)
    except ValueError as e:
        # Clean CLI failure (no traceback) for expected config/user errors.
        logger.error(str(e))
        raise SystemExit(2)

    if args.trace:
        logger.debug("TRACE")
        logger.debug("has snapshot=%s", _get_any(out_state, "fundamentals_snapshot") is not None)
        logger.debug("has bull_case=%s", _get_any(out_state, "bull_case") is not None)
        logger.debug("has bear_case=%s", _get_any(out_state, "bear_case") is not None)
        logger.debug("has debate_summary=%s", _get_any(out_state, "debate_summary") is not None)
        logger.debug("has report=%s", _get_any(out_state, "fundamentals_report") is not None)

    report = _get_any(out_state, "fundamentals_report")
    if report is None:
        raise RuntimeError("fundamentals_report is None (unexpected).")

    if args.output == "json":
        try:
            try:
                sys.stdout.reconfigure(write_through=True)
            except Exception:
                pass

            payload = out_state.model_dump() if hasattr(out_state, "model_dump") else dict(out_state)

            # Build explain contract once
            explain = _build_explain(out_state, cfg)

            # Attach explain at top-level (keeps existing payload behavior)
            payload["explain"] = explain

            # ALSO attach explain under fundamentals_report (tests expect this location)
            fr = payload.get("fundamentals_report")
            fr = _maybe_dump(fr) if fr is not None else {}
            if isinstance(fr, dict):
                fr["explain"] = explain
                payload["fundamentals_report"] = fr

            sys.stdout.write(json.dumps(payload, indent=args.json_indent, default=str) + "\n")
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
        nodes = _get_any(out_state, "trace_nodes")
        if nodes:
            logger.debug("NODE TRACE: %s", " → ".join(nodes))

        events = _get_any(out_state, "trace_events")
        if events:
            for line in events:
                logger.debug("TRACE EVENT: %s", line)


if __name__ == "__main__":
    main()
