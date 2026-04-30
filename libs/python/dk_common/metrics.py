from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["service", "method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["service", "method", "path"],
)


def setup_metrics(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def prometheus_http_metrics(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started
        path_template = _path_template(request)
        record_http_request(
            service_name=service_name,
            method=request.method,
            path_template=path_template,
            status_code=response.status_code,
            duration_seconds=duration,
        )
        return response

    if not any(getattr(route, "path", None) == "/metrics" for route in app.routes):
        app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=False)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_http_request(
    service_name: str,
    method: str,
    path_template: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(service_name, method, path_template, status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(service_name, method, path_template).observe(duration_seconds)


def _path_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return request.url.path
