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
    - LLM/agentic runtime configuration defaults from service environment variables
      (Copilot variables) when not provided by request.

Author:
    Kanir Pandya

Updated:
    2026-02-15
"""

from __future__ import annotations

import json
import logging
import os
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
    # Fundamentals provider (API -> engine)
    if req.provider:
        raw = (req.provider.value or "").strip().lower()

        # API contract names -> engine fundamentals provider names
        provider_map = {
            "yahoo": "yfinance",
            "yahoo_stub": "stub",
            # allow passing engine-native values too
            "yfinance": "yfinance",
            "stub": "stub",
        }
        engine_fund_provider = provider_map.get(raw, raw)

        # Engine expects this shape (see CLI: cfg.setdefault("providers", {})["fundamentals"] = ...)
        config.setdefault("providers", {})["fundamentals"] = engine_fund_provider

        # Optional: remove/ignore legacy flat key to avoid confusion
        # (harmless either way, but this keeps config clean)
        config.pop("provider", None)

    # Mode (unchanged)
    if req.mode:
        config["mode"] = req.mode.value  # Enum -> string

    # Force debate (unchanged)
    if req.force_debate is not None:
        config["force_debate"] = req.force_debate

    # Output (unchanged)
    if req.output:
        config["output"] = req.output


def _as_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return None

def _as_int(raw: str | None, *, default: int | None = None) -> int | None:
    """
    Parse an environment variable-ish value into an int.

    Accepts:
      - None / "" -> default
      - "30" -> 30
    Raises:
      ValueError for non-integer strings.
    """
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    return int(s)

def _apply_llm_env_defaults(config: Dict[str, Any]) -> None:
    """
    Apply LLM defaults from environment variables (Copilot/infra) for API requests.

    IMPORTANT:
      The engine's config schema may be either flat (llm_provider) or nested (llm.provider).
      We set both shapes defensively so the engine sees the provider/model in AWS.
    """
    provider = os.getenv("LLM_PROVIDER")
    model_identifier = os.getenv("LLM_MODEL_IDENTIFIER")
    timeout_seconds_raw = os.getenv("LLM_TIMEOUT_SECONDS")
    trace_enabled_raw = os.getenv("LLM_TRACE_ENABLED")

    timeout_seconds = _as_int(timeout_seconds_raw, default=30)
    trace_enabled = _as_bool(trace_enabled_raw)

    # Log (safe): provider + last segment of model identifier only.
    model_tail = (model_identifier.split("/")[-1] if model_identifier else None)
    logger.info(
        "LLM env defaults: provider=%s model=%s timeout=%s trace=%s",
        provider,
        model_tail,
        timeout_seconds,
        trace_enabled,
    )

    # ---- Flat keys (common in CLI configs) ----
    if provider:
        config.setdefault("llm_provider", provider)
    if model_identifier:
        config.setdefault("llm_model_identifier", model_identifier)
    if timeout_seconds is not None:
        config.setdefault("llm_timeout_seconds", timeout_seconds)
    if trace_enabled is not None:
        config.setdefault("llm_trace_enabled", trace_enabled)

    # ---- Nested keys (common in structured engine configs) ----
    llm_block = config.setdefault("llm", {})
    if isinstance(llm_block, dict):
        if provider:
            llm_block.setdefault("provider", provider)
        if model_identifier:
            llm_block.setdefault("model_identifier", model_identifier)
            llm_block.setdefault("model", model_identifier)  # some configs use "model"
        if timeout_seconds is not None:
            llm_block.setdefault("timeout_seconds", timeout_seconds)
            llm_block.setdefault("timeout", timeout_seconds)  # some configs use "timeout"
        if trace_enabled is not None:
            llm_block.setdefault("trace_enabled", trace_enabled)
            llm_block.setdefault("trace", trace_enabled)

        # One more common nesting: llm.client.*
        client_block = llm_block.setdefault("client", {})
        if isinstance(client_block, dict):
            if provider:
                client_block.setdefault("provider", provider)
            if model_identifier:
                client_block.setdefault("model_identifier", model_identifier)
                client_block.setdefault("model", model_identifier)
            if timeout_seconds is not None:
                client_block.setdefault("timeout_seconds", timeout_seconds)
                client_block.setdefault("timeout", timeout_seconds)


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

    # Default LLM runtime settings from env for API calls (Copilot variables).
    mode = config.get("mode")  # "det" | "llm" | "agentic"
    if mode in ("llm", "agentic"):
        _apply_llm_env_defaults(config)

    logger.info("analysis config (pre-engine): %s", config)

    try:
        logger.info("engine: starting run_analysis mode=%s provider=%s", config.get("mode"), config.get("providers"))
        result = run_analysis(ticker=req.ticker, config=config)
        logger.info(
            "engine: finished run_analysis trace_nodes=%s report_key_points=%s appendix_len=%s",
            getattr(result, "trace_nodes", None),
            len(getattr(getattr(result, "fundamentals_report", None), "key_points", []) or []),
            len(getattr(getattr(result, "fundamentals_report", None), "appendix", "") or ""),
        )

    except ValueError as e:
        msg = str(e)
        if "LLM mode requires an LLM provider" in msg:
            msg = (
                "LLM mode requires an LLM provider. "
                "Set LLM_PROVIDER (and optionally LLM_MODEL_IDENTIFIER, "
                "LLM_TIMEOUT_SECONDS, LLM_TRACE_ENABLED) in the service environment."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
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
