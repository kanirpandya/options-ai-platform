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
    2026-02-19
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

from backend.api.contracts.error_contract import ErrorResponse
from backend.api.schemas.analysis import AnalyzeRequest
from coveredcall_agents.llm.providers import LLMProvider
from backend.shared.models.normalization.engine_config_mapping import (
    apply_engine_overrides_from_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


# ---------------------------------------------------------------------------
# Env Parsing Helpers
# ---------------------------------------------------------------------------

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


def _set_if_empty(d: Dict[str, Any], key: str, value: Any) -> None:
    """
    Set d[key] if value is not None and the existing value is missing/empty.

    This avoids setdefault() pitfalls when defaults exist but are None.
    """
    if value is None:
        return
    cur = d.get(key, None)
    if cur is None or cur == "" or cur == {}:
        d[key] = value


def _canonicalize_llm_runtime(config: Dict[str, Any]) -> None:
    """
    Canonicalize LLM runtime fields into config["llm"].

    IMPORTANT:
      Intentionally OVERWRITES config["llm"]["provider"] etc when explicit overrides exist.
      This prevents DEFAULT_CONFIG values (e.g., provider="ollama") from shadowing test/env
      overrides like provider="mock".
    """
    llm_block = config.get("llm")
    if llm_block is None or not isinstance(llm_block, dict):
        llm_block = {}
        config["llm"] = llm_block

    client_block = llm_block.get("client")
    if client_block is None or not isinstance(client_block, dict):
        client_block = {}
        llm_block["client"] = client_block

    # Precedence: flat -> llm.client.* -> llm.*
    provider_raw = (
        config.get("llm_provider")
        or client_block.get("provider")
        or llm_block.get("provider")
    )
    model_identifier = (
        config.get("llm_model_identifier")
        or client_block.get("model_identifier")
        or llm_block.get("model_identifier")
        or client_block.get("model")
        or llm_block.get("model")
    )
    timeout_seconds = (
        config.get("llm_timeout_seconds")
        or client_block.get("timeout_seconds")
        or llm_block.get("timeout_seconds")
        or client_block.get("timeout")
        or llm_block.get("timeout")
        or llm_block.get("timeout_s")
    )
    trace_enabled_raw = (
        config.get("llm_trace_enabled")
        or client_block.get("trace_enabled")
        or llm_block.get("trace_enabled")
        or client_block.get("trace")
        or llm_block.get("trace")
    )

    # Normalize/validate provider via enum (but don't crash API if invalid)
    provider_value: str | None = None
    if provider_raw is not None:
        try:
            provider_value = LLMProvider(str(provider_raw).strip().lower()).value
        except Exception:
            provider_value = str(provider_raw).strip().lower()

    # Normalize trace to actual bool if possible
    trace_bool: bool | None
    if isinstance(trace_enabled_raw, bool) or trace_enabled_raw is None:
        trace_bool = trace_enabled_raw
    else:
        trace_bool = _as_bool(str(trace_enabled_raw))

    # OVERWRITE canonical fields when we have values
    if provider_value is not None:
        llm_block["provider"] = provider_value
        client_block["provider"] = provider_value

    if model_identifier is not None:
        llm_block["model_identifier"] = model_identifier
        llm_block["model"] = model_identifier
        client_block["model_identifier"] = model_identifier
        client_block["model"] = model_identifier

    if timeout_seconds is not None:
        llm_block["timeout_seconds"] = timeout_seconds
        llm_block["timeout"] = timeout_seconds
        client_block["timeout_seconds"] = timeout_seconds
        client_block["timeout"] = timeout_seconds

    if trace_bool is not None:
        llm_block["trace_enabled"] = trace_bool
        llm_block["trace"] = trace_bool
        client_block["trace_enabled"] = trace_bool
        client_block["trace"] = trace_bool


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

    timeout_seconds = _as_int(timeout_seconds_raw, default=None)
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
    _set_if_empty(config, "llm_provider", provider)
    _set_if_empty(config, "llm_model_identifier", model_identifier)
    _set_if_empty(config, "llm_timeout_seconds", timeout_seconds)
    _set_if_empty(config, "llm_trace_enabled", trace_enabled)

    # ---- Nested keys (common in structured engine configs) ----
    llm_block = config.get("llm")
    if llm_block is None or not isinstance(llm_block, dict):
        llm_block = {}
        config["llm"] = llm_block

    _set_if_empty(llm_block, "provider", provider)
    _set_if_empty(llm_block, "model_identifier", model_identifier)
    _set_if_empty(llm_block, "model", model_identifier)  # some configs use "model"
    _set_if_empty(llm_block, "timeout_seconds", timeout_seconds)
    _set_if_empty(llm_block, "timeout", timeout_seconds)  # some configs use "timeout"
    _set_if_empty(llm_block, "trace_enabled", trace_enabled)
    _set_if_empty(llm_block, "trace", trace_enabled)

    # One more common nesting: llm.client.*
    client_block = llm_block.get("client")
    if client_block is None or not isinstance(client_block, dict):
        client_block = {}
        llm_block["client"] = client_block

    _set_if_empty(client_block, "provider", provider)
    _set_if_empty(client_block, "model_identifier", model_identifier)
    _set_if_empty(client_block, "model", model_identifier)
    _set_if_empty(client_block, "timeout_seconds", timeout_seconds)
    _set_if_empty(client_block, "timeout", timeout_seconds)


# ---------------------------------------------------------------------------
# Base Config
# ---------------------------------------------------------------------------

def _base_config() -> Dict[str, Any]:
    """
    Return a deep-copied engine default config so API behavior matches CLI behavior
    and request overrides do not mutate module-level defaults.
    """
    try:
        from coveredcall_agents.config.default_config import DEFAULT_CONFIG  # type: ignore
    except Exception as e:
        logger.exception(
            "Failed to import engine DEFAULT_CONFIG; falling back to empty config: %s", e
        )
        return {}

    # Deep copy (JSON roundtrip) to avoid mutating DEFAULT_CONFIG
    return json.loads(json.dumps(DEFAULT_CONFIG))


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

    apply_engine_overrides_from_request(
        config,
        provider=(req.provider.value if req.provider else None),
        mode=(req.mode.value if req.mode else None),
        force_debate=req.force_debate,
        output=req.output,
    )

    # Default LLM runtime settings from env for API calls (Copilot variables).
    mode = config.get("mode")  # "det" | "llm" | "agentic"
    if mode in ("llm", "agentic"):
        _apply_llm_env_defaults(config)
        # Critical: ensure config["llm"]["provider"] reflects env/request overrides
        _canonicalize_llm_runtime(config)

    logger.info("analysis config (pre-engine): %s", config)

    # Helpful in AWS logs when debugging env/config drift
    logger.info(
        "LLM cfg check: llm_provider=%r llm.provider=%r llm.client.provider=%r model=%r",
        config.get("llm_provider"),
        (config.get("llm") or {}).get("provider") if isinstance(config.get("llm"), dict) else None,
        ((config.get("llm") or {}).get("client") or {}).get("provider")
        if isinstance(config.get("llm"), dict) and isinstance((config.get("llm") or {}).get("client"), dict)
        else None,
        config.get("llm_model_identifier")
        or ((config.get("llm") or {}).get("model_identifier") if isinstance(config.get("llm"), dict) else None),
    )

    try:
        logger.info(
            "engine: starting run_analysis mode=%s providers=%s",
            config.get("mode"),
            config.get("providers"),
        )
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
        # Avoid returning null config if engine model doesn't echo it for some modes.
        echoed_cfg = safe_payload.get("config")
        stable_cfg = echoed_cfg if isinstance(echoed_cfg, dict) else (config or {})

        return {
            "ticker": safe_payload.get("ticker"),
            "as_of": safe_payload.get("as_of"),
            "config": stable_cfg,
            "fundamentals_snapshot": safe_payload.get("fundamentals_snapshot"),
            "fundamentals_report": safe_payload.get("fundamentals_report"),
            "trace_nodes": safe_payload.get("trace_nodes"),
        }

    return {"result": safe_payload}