"""
tests.api.test_analyze

Purpose:
    API regression tests for /v1/analyze contract and validation envelope.

Covers:
    - Deterministic success path (no network)
    - Request validation envelope (422)
    - Unknown field rejection (422)
    - Invalid provider enum (422)

Notes:
    - Prefer provider="yahoo_stub" in tests to avoid yfinance network dependency.
    - Tests use client_factory (not client) to match current conftest fixtures.
    - If your app returns a custom 422 envelope, assert that stable contract here.
"""

from __future__ import annotations


def test_analyze_success(client_factory) -> None:
    client = client_factory()
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "mode": "det", "provider": "yahoo_stub"})
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["ticker"] == "AAPL"
    assert "as_of" in data
    assert "fundamentals_snapshot" in data
    assert "fundamentals_report" in data
    assert r.headers.get("x-request-id")


def test_analyze_missing_ticker_422_has_error_envelope(client_factory) -> None:
    client = client_factory()
    r = client.post("/v1/analyze", json={})
    assert r.status_code == 422, r.text

    data = r.json()
    # Custom validation envelope contract
    assert "request_id" in data
    assert data["error_code"] == "BAD_REQUEST"
    assert data["message"] == "Request validation failed"
    assert "details" in data
    assert "errors" in data["details"]
    assert r.headers.get("x-request-id")


def test_analyze_unknown_field_forbidden(client_factory) -> None:
    client = client_factory()
    # Intentionally misspelled field to trigger extra_forbidden
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "providre": "yahoo_stub"})
    assert r.status_code == 422, r.text

    data = r.json()
    errors = data["details"]["errors"]
    assert any(e.get("type") == "extra_forbidden" for e in errors)


def test_analyze_invalid_provider_enum(client_factory) -> None:
    client = client_factory()
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "provider": "not_real"})
    assert r.status_code == 422, r.text

    data = r.json()
    errors = data["details"]["errors"]
    # Friendly enum message contract
    assert any("Invalid provider" in (e.get("msg") or "") for e in errors)
