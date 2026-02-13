"""
CLI logging setup for coveredcall-agents.

Guarantees:
- ALL logging goes to stderr
- stdout is reserved exclusively for user-facing output / JSON
"""

from __future__ import annotations

import logging
import sys


def setup_cli_logging(*, trace: bool = False) -> None:
    # Remove any handlers already attached (important when running tests / notebooks)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    level = logging.DEBUG if trace else logging.INFO

    handler = logging.StreamHandler(sys.stderr)  # 🔒 force stderr
    handler.setLevel(level)

    formatter = logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)

    # Be explicit: no propagation surprises
    root.propagate = False
