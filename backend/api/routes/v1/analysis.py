"""
backend.api.routes.analysis

Purpose:
    FastAPI routes for analysis endpoints (e.g., POST /v1/analyze).
    Applies request-level overrides onto the base engine config and executes analysis.

Notes:
    - Exposes `router` for backend.api.main to include.
    - Keeps request schema (AnalyzeRequest) aligned with override logic.
    - Imports engine entrypoint inside the endpoint to avoid import-time failures.
    - Normalizes GraphState / Pydantic results into JSON-serializable dict.
    - Uses a safe JSON sanitizer to handle non-serializable types (e.g., functions).
    - Returns a stable, minimal API response (avoids leaking internal graph plumbing).
    - OpenAPI examples match runtime-cleaned validation messages.

Author:
    Kanir Pandya

Updated:
    2026-02-15
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from backend.api.schemas.analysis import AnalyzeRequest
from backend.api.contracts.error_contract import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])



# ---------------------------------------------------------------------------
# Config Handling
# ---------------------------------------------------------------------------

def _apply_overrides(config: Dict[str, Any], req: AnalyzeRequest) -> None:
    if req.provider:
        config["provider"] = req.provider.value  # Enum -> string

    if req.mode:
        config["mode"] = req.mode.value  # Enum -> string

    if req.force_debate is not None:
        config["force_debate"] = req.force_debate

    if req.output:
        config["output"] = req.output


def _base_config() -> Dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Safe JSON Conversion
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if callable(obj):
        name = getattr(obj, "__name__", obj.__class__.__name__)
        return f"<callable:{name}>"

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, (Path, UUID)):
        return str(obj)

    if isinstance(obj, (set, tuple)):
        return list(obj)

    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    return repr(obj)


def _to_safe_jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=_json_default))


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    responses={
        422: {
            "model": ErrorResponse,
            "description": "Request validation failed",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_required": {
                            "summary": "Missing required field",
                            "value": {
                                "request_id": "REQ_ID",
                                "error_code": "BAD_REQUEST",
                                "message": "Request validation failed",
                                "details": {
                                    "errors": [
                                        {
                                            "type": "missing",
                                            "loc": ["body", "ticker"],
                                            "msg": "Missing required field: ticker.",
                                            "input": {},
                                        }
                                    ]
                                },
                            },
                        },
                        "invalid_ticker": {
                            "summary": "Invalid ticker format",
                            "value": {
                                "request_id": "REQ_ID",
                                "error_code": "BAD_REQUEST",
                                "message": "Request validation failed",
                                "details": {
                                    "errors": [
                                        {
                                            "type": "value_error",
                                            "loc": ["body", "ticker"],
                                            "msg": "Invalid ticker format. Use letters/digits and optional '.' or '-' (1–12 chars).",
                                            "input": "$$$",
                                        }
                                    ]
                                },
                            },
                        },
                        "invalid_provider": {
                            "summary": "Invalid enum value",
                            "value": {
                                "request_id": "REQ_ID",
                                "error_code": "BAD_REQUEST",
                                "message": "Request validation failed",
                                "details": {
                                    "errors": [
                                        {
                                            "type": "enum",
                                            "loc": ["body", "provider"],
                                            "msg": "Invalid provider. Allowed values: yahoo, yahoo_stub.",
                                            "input": "not_real",
                                        }
                                    ]
                                },
                            },
                        },
                        "extra_field": {
                            "summary": "Unexpected field",
                            "value": {
                                "request_id": "REQ_ID",
                                "error_code": "BAD_REQUEST",
                                "message": "Request validation failed",
                                "details": {
                                    "errors": [
                                        {
                                            "type": "extra_forbidden",
                                            "loc": ["body", "providre"],
                                            "msg": "Unknown field: providre.",
                                            "input": "yahoo_stub",
                                        }
                                    ]
                                },
                            },
                        },
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "internal_error": {
                            "summary": "Unhandled server error",
                            "value": {
                                "request_id": "REQ_ID",
                                "error_code": "INTERNAL_ERROR",
                                "message": "Internal server error",
                                "details": None,
                            },
                        }
                    }
                }
            },
        },
    },
)
def analyze(req: AnalyzeRequest, request: Request) -> Dict[str, Any]:
    try:
        from coveredcall_agents.api.run_analysis import run_analysis  # type: ignore
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Engine entrypoint not available: {e}",
        ) from e

    config: Dict[str, Any] = _base_config()
    _apply_overrides(config, req)

    try:
        result = run_analysis(ticker=req.ticker, config=config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception:
        logger.exception("Unhandled error during analysis")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unhandled error during analysis.",
        )

    # Normalize result
    if hasattr(result, "model_dump"):
        payload: Any = result.model_dump()
    elif hasattr(result, "dict"):
        payload = result.dict()
    else:
        payload = result

    safe_payload = _to_safe_jsonable(payload)

    # Stable public API shape
    if isinstance(safe_payload, dict):
        return {
            "ticker": safe_payload.get("ticker"),
            "as_of": safe_payload.get("as_of"),
            "config": safe_payload.get("config", {}),
            "fundamentals_snapshot": safe_payload.get("fundamentals_snapshot"),
            "fundamentals_report": safe_payload.get("fundamentals_report"),
            "trace_nodes": safe_payload.get("trace_nodes"),
        }

    return {"result": safe_payload}
