from fastapi import FastAPI
from fastapi.testclient import TestClient

from dk_common.health import build_health_response, create_health_router


def test_build_health_response():
    assert build_health_response(
        service_name="svc",
        environment="test",
        version="1.0.0",
    ) == {
        "status": "ok",
        "service": "svc",
        "environment": "test",
        "version": "1.0.0",
    }


def test_build_health_response_uses_defaults():
    assert build_health_response("svc") == {
        "status": "ok",
        "service": "svc",
        "environment": "local",
        "version": None,
    }


def test_service_can_define_own_health_endpoint():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return build_health_response(
            service_name="kitchen-service",
            environment="local",
            version="0.1.0",
        )

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kitchen-service",
        "environment": "local",
        "version": "0.1.0",
    }


def test_create_health_router():
    app = FastAPI()
    app.include_router(create_health_router("svc", "test", "1.0.0"))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "svc",
        "environment": "test",
        "version": "1.0.0",
    }
