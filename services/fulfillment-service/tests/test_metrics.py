async def test_metrics_endpoint_exposes_http_and_fulfillment_metrics(client):
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "orders_created_total" in response.text
    assert "tasks_completed_total" in response.text
