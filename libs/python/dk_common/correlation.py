from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_request_id() -> str | None:
    return _request_id.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def _new_id() -> str:
    return str(uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        correlation_header: str = CORRELATION_ID_HEADER,
        request_header: str = REQUEST_ID_HEADER,
    ) -> None:
        super().__init__(app)
        self.correlation_header = correlation_header
        self.request_header = request_header

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(self.correlation_header) or _new_id()
        request_id = request.headers.get(self.request_header) or _new_id()

        correlation_token = _correlation_id.set(correlation_id)
        request_token = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(correlation_token)
            _request_id.reset(request_token)

        response.headers[self.correlation_header] = correlation_id
        response.headers[self.request_header] = request_id
        return response
