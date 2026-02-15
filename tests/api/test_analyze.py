"""
tests.api.test_analyze

Purpose:
    Smoke tests for /v1/analyze contract and validation envelope.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations


def test_analyze_success(client) -> None:
    r = client.post("/v1/analyze", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()

    assert data["ticker"] == "AAPL"
    assert "as_of" in data
    assert "fundamentals_snapshot" in data
    assert "fundamentals_report" in data
    assert r.headers.get("x-request-id")


def test_analyze_missing_ticker_422_has_error_envelope(client) -> None:
    r = client.post("/v1/analyze", json={})
    assert r.status_code == 422

    data = r.json()
    assert "request_id" in data
    assert data["error_code"] == "BAD_REQUEST"
    assert data["message"] == "Request validation failed"
    assert "details" in data
    assert "errors" in data["details"]
    assert r.headers.get("x-request-id")


def test_analyze_unknown_field_forbidden(client) -> None:
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "providre": "yahoo_stub"})
    assert r.status_code == 422

    data = r.json()
    errors = data["details"]["errors"]
    assert any(e.get("type") == "extra_forbidden" for e in errors)


def test_analyze_invalid_provider_enum(client) -> None:
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "provider": "not_real"})
    assert r.status_code == 422

    data = r.json()
    errors = data["details"]["errors"]
    # We normalized message; assert it contains our friendly enum message
    assert any("Invalid provider" in (e.get("msg") or "") for e in errors)
