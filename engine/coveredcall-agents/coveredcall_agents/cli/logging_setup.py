"""
clear/logging_setup.py

Configures CLI logging so:
- User output remains on stdout (handled elsewhere).
- Diagnostics/trace/debug go to stderr via logging.
- quiet suppresses stderr chatter (ERROR only).
- trace enables DEBUG.
"""

from __future__ import annotations

import logging
import sys


def setup_cli_logging(*, trace: bool = False, quiet: bool = False) -> None:
    """
    Configure logging for CLI runs.

    - quiet=True: only ERROR logs to stderr
    - trace=True: DEBUG logs to stderr
    - default: INFO logs to stderr
    """
    if quiet:
        level = logging.ERROR
    elif trace:
        level = logging.DEBUG
    else:
        level = logging.INFO

    root = logging.getLogger()

    # Remove existing handlers to avoid duplicate logs in pytest runs
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    root.addHandler(handler)
    root.setLevel(level)

    # Silence noisy third-party libs unless trace is enabled.
    if not trace:
        for name in ("httpx", "httpcore", "urllib3"):
            logging.getLogger(name).setLevel(logging.WARNING)

