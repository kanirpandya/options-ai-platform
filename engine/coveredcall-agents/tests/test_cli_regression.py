"""
test_cli_regression.py

Purpose:
    Regression and sanity tests for the CLI covering deterministic, LLM,
    and debate modes.

Role in system:
    Acts as a safety net to ensure stdout JSON purity, explain/appendix
    completeness, timeout fallbacks, quiet-mode behavior, and BrokenPipe safety.

Notes:
    These tests intentionally shell out to the CLI instead of importing internals
    to validate true end-to-end behavior.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from coveredcall_agents.fundamentals.mode import FundamentalsMode


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RunResult:
    code: int
    out: str
    err: str


def run_cli(*args: str, env_extra: dict[str, str] | None = None) -> RunResult:
    """
    Run: python -m cli.main <args>
    Captures stdout/stderr, never raises (we assert in tests).
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    p = subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return RunResult(code=p.returncode, out=p.stdout, err=p.stderr)


def parse_report(stdout: str) -> dict:
    s = (stdout or "").strip()
    assert s, "EMPTY STDOUT"
    j = json.loads(s)
    return j.get("fundamentals_report", j)


def test_deterministic_core_json() -> None:
    rr = run_cli("--ticker", "AAPL", "--fundamentals-mode", "deterministic", "--output", "json")
    assert rr.code == 0, rr.err
    r = parse_report(rr.out)
    assert r["stance"]
    assert r["covered_call_bias"]
    assert 0.0 <= float(r["confidence"]) <= 1.0


def test_llm_explain_core_present() -> None:
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.LLM.value,
        "--llm-provider",
        "ollama",
        "--llm-model",
        "llama3.2:3b",
        "--llm-timeout-s",
        "180",
        "--output",
        "json",
    )
    assert rr.code == 0, rr.err
    r = parse_report(rr.out)
    e = r.get("explain") or {}

    # shape contract
    for k in [
        "det_fundamentals",
        "llm_fundamentals",
        "divergence_report",
        "divergence_reasons",
        "mode",
        "trace_nodes",
    ]:
        assert k in e, f"missing explain.{k}"

    # core presence
    assert e.get("det_fundamentals"), "missing det_fundamentals"
    assert e.get("llm_fundamentals"), "missing llm_fundamentals"
    assert e.get("divergence_report"), "missing divergence_report"


def test_llm_provider_none_fails_cleanly() -> None:
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.LLM.value,
        "--llm-provider",
        "none",
        "--output",
        "json",
    )
    assert rr.code != 0, "expected nonzero exit code"
    assert "LLM mode requires an LLM provider" in rr.err, (
        "expected a clear error message on stderr\n"
        f"stdout={rr.out!r}\n"
        f"stderr={rr.err!r}"
    )


def test_force_debate_appendix_contains_blocks_180s() -> None:
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.LLM.value,
        "--force-debate",
        "--llm-provider",
        "ollama",
        "--llm-model",
        "llama3.2:3b",
        "--llm-timeout-s",
        "180",
        "--output",
        "json",
    )
    assert rr.code == 0, rr.err
    r = parse_report(rr.out)
    a = r.get("appendix") or ""
    assert "DIVERGENCE REPORT" in a, "appendix missing divergence report"
    assert "LLM Debate Summary" in a, "appendix missing debate block"


def test_force_debate_explain_contains_debate_artifacts() -> None:
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.LLM.value,
        "--force-debate",
        "--llm-provider",
        "ollama",
        "--llm-model",
        "llama3.2:3b",
        "--llm-timeout-s",
        "180",
        "--output",
        "json",
    )
    assert rr.code == 0, rr.err
    r = parse_report(rr.out)
    e = r.get("explain") or {}
    assert e.get("debate_summary") is not None, "missing debate_summary"
    assert e.get("bull_case") is not None, "missing bull_case"
    assert e.get("bear_case") is not None, "missing bear_case"


def test_no_json_payload_leaks_to_stderr_in_json_mode() -> None:
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.LLM.value,
        "--force-debate",
        "--llm-provider",
        "ollama",
        "--llm-model",
        "llama3.2:3b",
        "--llm-timeout-s",
        "180",
        "--output",
        "json",
    )
    assert rr.code == 0, rr.err
    _ = parse_report(rr.out)

    # stderr should not contain the JSON payload marker
    assert '"fundamentals_report"' not in rr.err, "stderr leaked JSON payload"


def test_quiet_suppresses_stderr() -> None:
    # Use deterministic mode to avoid environment-dependent LLM timeout warnings.
    rr = run_cli(
        "--ticker",
        "AAPL",
        "--fundamentals-mode",
        FundamentalsMode.DETERMINISTIC.value,
        "--quiet",
        "--output",
        "json",
    )
    assert rr.code == 0, rr.err
    _ = parse_report(rr.out)
    assert (rr.err or "").strip() == "", f"quiet still produced stderr: {rr.err[:200]}"


def test_broken_pipe_does_not_crash() -> None:
    """
    Simulate downstream consumer closing early (like: | head -c 1).
    We can't perfectly reproduce SIGPIPE handling cross-platform with subprocess pipes,
    but this at least ensures the process exits cleanly when stdout isn't consumed.
    """
    p = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "cli.main",
            "--ticker",
            "AAPL",
            "--fundamentals-mode",
            FundamentalsMode.LLM.value,
            "--llm-provider",
            "ollama",
            "--llm-model",
            "llama3.2:3b",
            "--llm-timeout-s",
            "180",
            "--output",
            "json",
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    assert p.stdout is not None
    assert p.stderr is not None

    # Read 1 byte and close early
    _ = p.stdout.read(1)
    p.stdout.close()

    code = p.wait(timeout=60)
    err = (p.stderr.read() or b"").decode("utf-8", errors="replace")

    # exit 0 preferred; some platforms may return 141 (SIGPIPE).
    assert code in (0, 141), f"unexpected exit={code} stderr={err[:400]}"
