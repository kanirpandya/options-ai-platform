"""
coveredcall_agents.llm.providers

Purpose:
    Canonical LLM provider identifiers supported by the engine.
    Used by CLI + API config validation and by provider factory selection.

Author:
    Kanir Pandya

Created:
    2026-02-19
"""

from __future__ import annotations

from enum import Enum


class LLMProvider(str, Enum):
    STUB = "stub"
    MOCK = "mock"
    OLLAMA = "ollama"
    BEDROCK = "bedrock"
