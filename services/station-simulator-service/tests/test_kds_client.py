import httpx
import pytest
import json

from app.kds_client.client import KdsClient
from app.kds_client.schemas import ClaimConflict, RetryableKdsError


def task_payload():
    return {
        "kds_task_id": 1,
        "task_id": "task-1",
        "order_id": "order-1",
        "station_id": 1,
        "operation": "cook_patty",
        "menu_item_name": "Burger",
        "status": "displayed",
        "estimated_duration_seconds": 480,
        "pickup_deadline": None,
        "displayed_at": "2026-04-30T10:00:00Z",
    }


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/kds/stations/1/tasks"),
        ("POST", "/kds/stations/1/tasks/task-1/claim"),
        ("POST", "/kds/stations/1/tasks/task-1/complete"),
    ],
)
async def test_client_sends_correlation_headers(method, path):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Correlation-ID"] == "corr-1"
        assert request.headers["X-Request-ID"]
        if method == "GET":
            return httpx.Response(200, json=[task_payload()])
        payload = task_payload() | {"status": "claimed", "claimed_by": "worker-1", "claimed_at": "2026-04-30T10:01:00Z"}
        if path.endswith("/complete"):
            payload = payload | {"status": "completed", "completed_at": "2026-04-30T10:02:00Z"}
        return httpx.Response(200, json=payload)

    client = KdsClient("http://kitchen")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://kitchen")
    try:
        if method == "GET":
            await client.get_station_tasks(1, "corr-1")
        elif path.endswith("/claim"):
            await client.claim_task(1, "task-1", "worker-1", "corr-1")
        else:
            await client.complete_task(1, "task-1", "worker-1", "corr-1")
    finally:
        await client.close()


async def test_claim_sends_worker_id():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/kds/stations/1/tasks/task-1/claim"
        assert json.loads((await request.aread()).decode()) == {"station_worker_id": "worker-1"}
        return httpx.Response(
            200,
            json=task_payload() | {"status": "claimed", "claimed_by": "worker-1", "claimed_at": "2026-04-30T10:01:00Z"},
        )

    client = KdsClient("http://kitchen")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://kitchen")
    try:
        response = await client.claim_task(1, "task-1", "worker-1", "corr-1")
    finally:
        await client.close()

    assert response.status == "claimed"


async def test_claim_conflict_is_typed():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "task_already_claimed"})

    client = KdsClient("http://kitchen")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://kitchen")
    try:
        with pytest.raises(ClaimConflict) as exc:
            await client.claim_task(1, "task-1", "worker-1", "corr-1")
    finally:
        await client.close()

    assert exc.value.reason == "task_already_claimed"


async def test_5xx_is_retryable():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "fulfillment_service_unavailable"})

    client = KdsClient("http://kitchen")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://kitchen")
    try:
        with pytest.raises(RetryableKdsError):
            await client.get_station_tasks(1, "corr-1")
    finally:
        await client.close()
