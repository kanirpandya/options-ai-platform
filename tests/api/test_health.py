"""
tests.api.test_health

Purpose:
    Smoke tests for health endpoints.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations


def test_health_root_ok(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert r.headers.get("x-request-id")


def test_health_v1_ok(client) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers.get("x-request-id")
