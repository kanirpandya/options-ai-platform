"""
Shim entrypoint for coveredcall-agents.

Purpose:
    Forward to the canonical CLI implementation at:
        coveredcall_agents/cli/main.py

Notes:
    Keep this file logic-free to avoid divergence between multiple CLI entrypoints.

Author:
    Kanir Pandya

Created:
    2026-02-19
"""
from __future__ import annotations

from coveredcall_agents.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
