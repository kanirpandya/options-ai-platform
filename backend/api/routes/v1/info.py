"""
backend.api.routes.v1.info

Purpose:
    Versioned info endpoint that exposes API metadata and supported options
    for client discovery (providers/modes/etc).

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["info"])


@router.get("/info")
def info() -> dict:
    # Keep this as stable contract; safe for clients to depend on.
    return {
        "api_version": "v1",
        "service": "options-ai-platform",
        "endpoints": {
            "analyze": "/v1/analyze",
            "health": "/v1/health",
        },
        # Keep in sync with your AnalyzeRequest enums.
        "supported": {
            "providers": ["yahoo", "yahoo_stub"],
            "modes": ["det", "llm", "agentic"],
            "output": ["pretty", "json"],
        },
    }
