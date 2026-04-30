async def test_health_returns_service_status(client):
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "station-simulator-service"


async def test_metrics_endpoint_exposes_simulator_metrics(client):
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "simulator_claim_attempts_total" in response.text


async def test_workers_endpoint_returns_configured_workers(client):
    response = await client.get("/simulator/workers")

    assert response.status_code == 200
    assert response.json() == []
