from fastapi import FastAPI
from fastapi.testclient import TestClient

from dk_common.metrics import setup_metrics


def test_setup_metrics_adds_metrics_endpoint():
    app = FastAPI()
    setup_metrics(app, service_name="test-service")

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text


def test_http_metrics_use_route_template_not_raw_path():
    app = FastAPI()

    @app.get("/orders/{order_id}")
    async def get_order(order_id: str):
        return {"order_id": order_id}

    setup_metrics(app, service_name="test-service")

    client = TestClient(app)
    response = client.get("/orders/14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e")
    assert response.status_code == 200

    metrics = client.get("/metrics").text
    assert 'path="/orders/{order_id}"' in metrics
    assert "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e" not in metrics
