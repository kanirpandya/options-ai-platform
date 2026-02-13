"""
Basic smoke tests for the CLI.

Purpose:
- Verifies the CLI runs end-to-end without crashing.
- Ensures minimal valid output is produced for core modes.
- Catches obvious wiring/import/runtime errors early.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from coveredcall_agents.fundamentals.mode import FundamentalsMode

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "coveredcall_agents.cli.main"]

TICKER = os.environ.get("TICKER", "AAPL")
MODEL = os.environ.get("MODEL", "llama3.2:3b")
TIMEOUT = os.environ.get("TIMEOUT", "180")

SMOKE_LLM = os.environ.get("SMOKE_LLM", "0") == "1"

BAD_MARKERS = ["[DEBUG", "[OllamaClient]", "Fundamentals provider:", "Fundamentals mode:"]


def run(args):
    return subprocess.run(
        CLI + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def assert_stdout_clean_json(r: subprocess.CompletedProcess):
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    for m in BAD_MARKERS:
        assert m not in r.stdout, f"stdout polluted with {m}"
    return j


def test_json_stdout_is_clean_deterministic():
    r = run(["--ticker", TICKER, "--fundamentals-mode", "deterministic", "--output", "json"])
    j = assert_stdout_clean_json(r)
    assert j.get("fundamentals_report") is not None


def test_trace_emits_debug_to_stderr_only_deterministic():
    r = run(
        ["--ticker", TICKER, "--fundamentals-mode", "deterministic", "--trace", "--output", "json"]
    )
    assert_stdout_clean_json(r)
    assert any(m in r.stderr for m in ("[DEBUG", "[OllamaClient]")), (
        "trace did not emit debug to stderr"
    )


def test_broken_pipe_safety():
    # head closes pipe early; program should exit 0
    p1 = subprocess.Popen(
        CLI + ["--ticker", TICKER, "--output", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    subprocess.run(
        ["head", "-n", "1"],
        stdin=p1.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    p1.stdout.close()
    _, err = p1.communicate()
    assert p1.returncode == 0, err


# -----------------------------
# Optional LLM integration tests
# -----------------------------


def test_json_stdout_is_clean_llm_optional():
    if not SMOKE_LLM:
        return

    r = run(
        [
            "--ticker",
            TICKER,
            "--fundamentals-mode",
            FundamentalsMode.LLM.value,
            "--force-debate",
            "--llm-provider",
            "ollama",
            "--llm-model",
            MODEL,
            "--llm-timeout-s",
            TIMEOUT,
            "--output",
            "json",
        ]
    )
    j = assert_stdout_clean_json(r)
    appendix = (j.get("fundamentals_report") or {}).get("appendix")
    assert appendix and len(appendix) > 0, "appendix missing/empty"
