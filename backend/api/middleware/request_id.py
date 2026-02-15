"""
backend.api.middleware.request_id

Purpose:
    Middleware that ensures each request has a request-id and propagates it to responses.

Author:
    Kanir Pandya

Created:
    2026-02-15
"""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from backend.api.logging.request_context import request_id_ctx_var


from backend.api.contracts.request_id_policy import RequestIdPolicy


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, policy: RequestIdPolicy | None = None) -> None:
        super().__init__(app)
        self._policy = policy or RequestIdPolicy()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        policy = self._policy

        incoming = (
            request.headers.get(policy.request_id_header)
            or request.headers.get(policy.correlation_id_header)
        )

        request_id = incoming if incoming else str(uuid.uuid4())

        # Attach for handlers/logging
        request.state.request_id = request_id
        request_id_ctx_var.set(request_id)

        response: Response = await call_next(request)

        # Echo back for client correlation
        response.headers[policy.response_header] = request_id
        return response
