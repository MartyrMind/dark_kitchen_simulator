from fastapi import FastAPI
from fastapi.testclient import TestClient

from dk_common.correlation import (
    CorrelationIdMiddleware,
    get_correlation_id,
    get_request_id,
)


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ids")
    async def ids():
        return {
            "correlation_id": get_correlation_id(),
            "request_id": get_request_id(),
        }

    return app


def test_existing_correlation_id_is_returned():
    response = TestClient(create_app()).get(
        "/ids",
        headers={"X-Correlation-ID": "corr-1", "X-Request-ID": "req-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-1"
    assert response.headers["X-Request-ID"] == "req-1"
    assert response.json() == {
        "correlation_id": "corr-1",
        "request_id": "req-1",
    }


def test_missing_ids_are_generated_and_do_not_leak_between_requests():
    client = TestClient(create_app())

    first = client.get("/ids")
    second = client.get("/ids")

    assert first.headers["X-Correlation-ID"]
    assert first.headers["X-Request-ID"]
    assert second.headers["X-Correlation-ID"]
    assert second.headers["X-Request-ID"]
    assert first.headers["X-Correlation-ID"] != second.headers["X-Correlation-ID"]
    assert first.json()["correlation_id"] == first.headers["X-Correlation-ID"]
    assert second.json()["request_id"] == second.headers["X-Request-ID"]
