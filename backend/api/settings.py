# backend/api/settings.py
"""
backend.api.settings

Purpose:
    Centralized configuration for the FastAPI service.
    Keeps deployment flexible and avoids hard-coded app metadata.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.api.contracts.api_paths import ApiPaths


class Settings(BaseModel):
    service_name: str = Field(default="options-ai-platform-api")
    service_version: str = Field(default="0.1.0")

    api_v1_prefix: str = Field(default=ApiPaths().v1_prefix)

    max_request_timeout_s: int = Field(default=120)


def get_settings() -> Settings:
    # Later: switch to pydantic-settings for env var loading if desired.
    return Settings()
