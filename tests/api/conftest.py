"""
tests.api.conftest

Shared pytest fixtures for API tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Adjust this import if create_app lives somewhere else
from backend.api.main import create_app


@pytest.fixture()
def client_factory():
    """
    Factory fixture that creates a fresh TestClient.

    IMPORTANT:
        Used when tests need to set env vars before app creation
        (e.g., LLM tests).
    """

    def _make() -> TestClient:
        app = create_app()
        return TestClient(app, raise_server_exceptions=True)

    return _make


@pytest.fixture()
def client(client_factory) -> TestClient:
    """
    Backward-compatible alias fixture.

    Allows simple tests (health, basic analyze) to just depend on `client`
    without worrying about env timing.
    """
    return client_factory()
