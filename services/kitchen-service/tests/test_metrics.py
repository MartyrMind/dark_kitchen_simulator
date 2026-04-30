async def test_metrics_endpoint_exposes_http_and_kds_metrics(client):
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "kds_claim_attempts_total" in response.text
    assert "station_busy_slots" in response.text
