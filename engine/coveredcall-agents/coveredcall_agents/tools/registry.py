from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class Tools:
    """
    Typed-ish tool bundle passed through GraphState.
    Keep this module free of imports from graph/* to avoid circular imports.
    """

    get_fundamental_snapshot: Callable[[str, datetime], Any]
