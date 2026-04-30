async def test_metrics_endpoint_exposes_http_metrics(client):
    await client.get("/health")
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert 'service="menu-service"' in response.text
