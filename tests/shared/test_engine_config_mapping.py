"""
tests.shared.test_engine_config_mapping

Purpose:
    Regression tests for centralized API→engine config normalization.
    Ensures mapping stays aligned with shared enums and engine contract.
"""

from __future__ import annotations

from backend.shared.models.enums import FundamentalsMode
from backend.shared.models.normalization.engine_config_mapping import (
    apply_engine_overrides_from_request,
    map_fundamentals_mode_to_engine,
    map_fundamentals_provider_to_engine,
)


def test_map_provider_known_values() -> None:
    assert map_fundamentals_provider_to_engine("yahoo") == "yfinance"
    assert map_fundamentals_provider_to_engine("yahoo_stub") == "stub"
    assert map_fundamentals_provider_to_engine("yfinance") == "yfinance"
    assert map_fundamentals_provider_to_engine("stub") == "stub"


def test_map_mode_enum_values() -> None:
    # Canonical enum values
    assert map_fundamentals_mode_to_engine(FundamentalsMode.DET.value) == "det"
    assert map_fundamentals_mode_to_engine(FundamentalsMode.LLM.value) == "llm"
    assert map_fundamentals_mode_to_engine(FundamentalsMode.AGENTIC.value) == "agentic"

    # Alias enum (same underlying value)
    assert map_fundamentals_mode_to_engine(FundamentalsMode.DETERMINISTIC.value) == "det"


def test_map_mode_string_alias() -> None:
    # Mapping-layer alias (API-level convenience)
    assert map_fundamentals_mode_to_engine("deterministic") == "det"


def test_unknown_passthrough() -> None:
    # Forward compatibility: unknown values pass through normalized
    assert map_fundamentals_mode_to_engine("future_mode") == "future_mode"
    assert map_fundamentals_provider_to_engine("future_provider") == "future_provider"


def test_apply_engine_overrides_from_request() -> None:
    cfg: dict = {}

    apply_engine_overrides_from_request(
        cfg,
        provider="yahoo_stub",
        mode=FundamentalsMode.DET.value,
        force_debate=True,
        output="json",
    )

    assert cfg["providers"]["fundamentals"] == "stub"
    assert cfg["mode"] == "det"
    assert cfg["force_debate"] is True
    assert cfg["output"] == "json"
