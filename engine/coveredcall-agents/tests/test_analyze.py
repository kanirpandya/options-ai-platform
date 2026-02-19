"""
tests/api/test_analyze.py

Purpose:
    API regression tests for /v1/analyze.

Covers:
    - Request validation envelope (422)
    - Unknown field rejection
    - Deterministic success path (no network)
    - LLM path returns non-empty, schema-compliant output
    - force_debate produces appendix content

Notes:
    - Prefer provider="yahoo_stub" in tests to avoid yfinance network dependency.
    - For LLM tests, env vars must be set BEFORE create_app() runs.
      We therefore build a fresh client via the shared client_factory fixture
      (defined in tests/api/conftest.py) after monkeypatching env vars.
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
    assert r.status_code == 422
    assert "detail" in r.json()


def test_analyze_unknown_field_forbidden(client_factory) -> None:
    client = client_factory()
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "unknown_field": 123})
    assert r.status_code in (400, 422), r.text


def test_analyze_invalid_provider_enum(client_factory) -> None:
    client = client_factory()
    r = client.post("/v1/analyze", json={"ticker": "AAPL", "provider": "nope"})
    assert r.status_code == 422


def test_analyze_llm_mode_returns_key_points_and_snapshot_metadata(client_factory, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL_IDENTIFIER", "mock")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("LLM_TRACE_ENABLED", "0")

    client = client_factory()
    resp = client.post("/v1/analyze", json={"ticker": "AAPL", "mode": "llm", "provider": "yahoo_stub"})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    snap = data["fundamentals_snapshot"]
    assert snap["as_of"] is not None
    assert snap["source"] is not None
    assert snap["metadata"] is not None

    report = data["fundamentals_report"]
    assert report is not None

    kps = report["key_points"]
    assert isinstance(kps, list)
    assert len(kps) == 4
    assert all(isinstance(x, str) and x.strip() for x in kps)


def test_analyze_llm_force_debate_includes_appendix(client_factory, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL_IDENTIFIER", "mock")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("LLM_TRACE_ENABLED", "0")

    client = client_factory()
    resp = client.post(
        "/v1/analyze",
        json={"ticker": "AAPL", "mode": "llm", "provider": "yahoo_stub", "force_debate": True},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    report = data["fundamentals_report"]
    appendix = report.get("appendix")
    assert appendix is not None
    assert "DIVERGENCE REPORT" in appendix
    assert "LLM Debate Summary" in appendix
