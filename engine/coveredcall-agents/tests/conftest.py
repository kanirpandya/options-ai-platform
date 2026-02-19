"""
engine.coveredcall-agents.tests.conftest

Purpose:
    Local pytest fixtures for coveredcall-agents engine tests.
    Keeps fixtures discoverable when running pytest from the monorepo root.

Author:
    Kanir Pandya

Created:
    2026-02-19
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app


@pytest.fixture()
def client_factory():
    """
    Factory fixture that creates a fresh TestClient.

    IMPORTANT:
        Used when tests need to set env vars before app creation (e.g., LLM tests).
    """

    def _make() -> TestClient:
        app = create_app()
        return TestClient(app, raise_server_exceptions=True)

    return _make


@pytest.fixture()
def client(client_factory) -> TestClient:
    """Back-compat alias for simple tests."""
    return client_factory()
