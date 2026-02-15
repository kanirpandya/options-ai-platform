# backend/api/routes/analysis.py
"""
backend.api.routes.analysis

Purpose:
    HTTP endpoints that wrap the coveredcall-agents analysis pipeline.

Design Notes:
    - Step 1: Sanitize engine output (datetime -> ISO, callables -> string) for JSON safety
    - Step 2: Public API contract is schema-driven (AnalyzeResponseV1 fields)
    - Step 3: Typed response model for /v1/analyze; debug endpoint returns full sanitized state

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

import datetime as dt
import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.api.contracts.api_paths import ApiPaths
from backend.api.contracts.config_mapping import ConfigPaths
from backend.api.contracts.sanitize_policy import SanitizePolicy
from backend.api.models import AnalyzeRequest, AnalyzeResponseV1
from backend.api.settings import get_settings
from backend.api.contracts.api_tags import ApiTags

from coveredcall_agents.api.run_analysis import run_analysis
from coveredcall_agents.config.default_config import DEFAULT_CONFIG

_settings = get_settings()
_paths = ApiPaths()
_cfgpaths = ConfigPaths()
_policy = SanitizePolicy()

router = APIRouter(prefix=_settings.api_v1_prefix, tags=["analysis"])


def _get_in(d: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _set_in(d: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur: dict[str, Any] = d
    for k in path[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[path[-1]] = value


def _set_first_matching_path(
    config: dict[str, Any],
    candidates: tuple[tuple[str, ...], ...],
    value: Any,
) -> None:
    for p in candidates:
        # p[:-1] is container; if it exists, prefer that structure
        if _get_in(config, p[:-1]) is not None:
            _set_in(config, p, value)
            return
    # fallback to first candidate
    _set_in(config, candidates[0], value)


def _apply_overrides(config: dict[str, Any], req: AnalyzeRequest) -> None:
    if req.provider:
        _set_first_matching_path(config, _cfgpaths.fundamentals_provider_candidates, req.provider)

    if req.mode:
        _set_first_matching_path(config, _cfgpaths.fundamentals_mode_candidates, req.mode)

    if req.force_debate:
        _set_first_matching_path(config, _cfgpaths.debate_force_candidates, True)

    if req.config_overrides:
        config.update(req.config_overrides)


def _json_sanitize(value: Any, *, _depth: int = 0) -> Any:
    if _depth > _policy.max_depth:
        return _policy.max_depth_token

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {str(k): _json_sanitize(v, _depth=_depth + 1) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_sanitize(v, _depth=_depth + 1) for v in value]

    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return _json_sanitize(value.model_dump(), _depth=_depth + 1)
        except Exception:
            return repr(value)

    if callable(value):
        name = getattr(value, "__name__", value.__class__.__name__)
        return f"{_policy.callable_prefix}{name}{_policy.callable_suffix}"

    return repr(value)


def _extract_public_response(state: dict[str, Any]) -> dict[str, Any]:
    fields = AnalyzeResponseV1.model_fields.keys()
    return {k: state.get(k) for k in fields if k in state}


@router.post(_paths.analyze, response_model=AnalyzeResponseV1)
def analyze(req: AnalyzeRequest) -> AnalyzeResponseV1:
    config: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
    _apply_overrides(config, req)

    try:
        result = run_analysis(ticker=req.ticker, config=config)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse(status_code=500, content={"error": str(e), "trace_tail": tb.splitlines()[-40:]})

    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        raw_state: Any = result.model_dump()
    elif isinstance(result, dict):
        raw_state = result
    else:
        raw_state = {"value": result}

    safe_state = _json_sanitize(raw_state)
    public_state = _extract_public_response(safe_state)

    return AnalyzeResponseV1.model_validate(public_state)


@router.post(_paths.analyze_debug)
def analyze_debug(req: AnalyzeRequest):
    config: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
    _apply_overrides(config, req)

    try:
        result = run_analysis(ticker=req.ticker, config=config)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "trace_tail": tb.splitlines()[-40:],
                "effective_config": _json_sanitize(config),
            },
        )

    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        raw_state: Any = result.model_dump()
    elif isinstance(result, dict):
        raw_state = result
    else:
        raw_state = {"value": result}

    return JSONResponse(status_code=200, content={"result": _json_sanitize(raw_state)})
