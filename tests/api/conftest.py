"""
tests.api.conftest

Purpose:
    Shared pytest fixtures for API smoke tests.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)
