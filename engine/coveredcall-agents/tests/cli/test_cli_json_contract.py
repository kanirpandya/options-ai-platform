"""
tests/cli/test_cli_json_contract.py

Purpose:
    CLI regression test to ensure `coveredcall-agents --output json`:
      - emits clean JSON on stdout
      - includes the stable explain contract at fundamentals_report.explain
      - does not leak debug strings to stdout

Author:
    Kanir Pandya

Created:
    2026-02-19
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def test_cli_output_json_has_explain_mode_and_clean_stdout() -> None:
    env = os.environ.copy()

    # Ensure local checkout is importable for module execution.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env["PYTHONPATH"] = repo_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    cmd = [
        sys.executable,
        "-m",
        "coveredcall_agents.cli.main",
        "--ticker",
        "AAPL",
        "--output",
        "json",
    ]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)

    assert p.returncode == 0, f"rc={p.returncode}\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}"

    s = p.stdout.strip()
    assert s.startswith("{"), f"stdout not JSON object start:\n{s[:200]}"
    payload = json.loads(s)

    fr = payload.get("fundamentals_report")
    assert isinstance(fr, dict), f"fundamentals_report not dict: {type(fr)}"
    explain = fr.get("explain")
    assert isinstance(explain, dict), f"fundamentals_report.explain not dict: {type(explain)}"
    mode = explain.get("mode")
    assert mode, f"explain.mode missing/empty: {mode!r}"

    # No accidental debug markers in stdout.
    for marker in ("DBG ", "DEBUG CLI:"):
        assert marker not in p.stdout, f"Found debug marker {marker!r} in stdout"
