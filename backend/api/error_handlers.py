"""
backend.api.error_handlers

Purpose:
    Register global exception handlers to return stable ErrorResponse objects.
    Ensures request_id is always included.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.contracts.error_contract import ApiErrorCode, ErrorResponse
from backend.api.errors import ApiError
from backend.api.logging.request_context import request_id_ctx_var

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    rid = getattr(getattr(request, "state", None), "request_id", None)
    if isinstance(rid, str) and rid:
        return rid

    rid2 = request_id_ctx_var.get()
    if isinstance(rid2, str) and rid2:
        return rid2

    return "-"


import re
from typing import Any

import re
from typing import Any

def _clean_validation_errors(errors: Any) -> Any:
    """
    Clean Pydantic/FastAPI validation errors for stable client-facing responses.

    - Strip "Value error, " prefix
    - Rewrite enum messages into "Invalid <field>. Allowed values: a, b."
    - Rewrite missing required into "Missing required field: <field>."
    - Rewrite extra forbidden into "Unknown field: <field>."
    - Drop ctx entirely for minimal/stable payloads
    """
    if not isinstance(errors, list):
        return errors

    for err in errors:
        if not isinstance(err, dict):
            continue

        err_type = err.get("type")
        loc = err.get("loc", [])
        msg = err.get("msg")

        # Strip noisy prefix from validator ValueErrors
        if isinstance(msg, str):
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, ") :]
            elif msg.startswith("Value error,"):
                msg = msg[len("Value error,") :].lstrip()
            err["msg"] = msg

        # Helper: last element of loc is usually the field name (e.g., "ticker", "provider")
        field_name = None
        if isinstance(loc, list) and len(loc) >= 2:
            field_name = loc[-1]

        # Rewrite enum messages
        if err_type == "enum" and isinstance(err.get("msg"), str) and field_name:
            original = err["msg"]
            options = re.findall(r"'([^']+)'", original)
            if options:
                err["msg"] = f"Invalid {field_name}. Allowed values: {', '.join(options)}."

        # Rewrite missing required field
        if err_type == "missing" and field_name:
            err["msg"] = f"Missing required field: {field_name}."

        # Rewrite extra forbidden field
        if err_type == "extra_forbidden" and field_name:
            err["msg"] = f"Unknown field: {field_name}."

        # Always drop ctx to keep payload minimal/stable
        err.pop("ctx", None)

    return errors



def register_error_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers on the FastAPI app.
    """

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = _get_request_id(request)

        safe_errors = jsonable_encoder(exc.errors())
        safe_errors = _clean_validation_errors(safe_errors)

        payload = ErrorResponse(
            request_id=rid,
            error_code=ApiErrorCode.BAD_REQUEST,
            message="Request validation failed",
            details={"errors": safe_errors},
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        rid = _get_request_id(request)
        payload = ErrorResponse(
            request_id=rid,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception in API request", exc_info=exc)

        rid = _get_request_id(request)
        payload = ErrorResponse(
            request_id=rid,
            error_code=ApiErrorCode.INTERNAL_ERROR,
            message="Internal server error",
            details=None,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())
