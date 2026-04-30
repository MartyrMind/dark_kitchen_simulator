from datetime import datetime

import httpx
from dk_common.correlation import get_correlation_id, get_request_id

from app.config import settings


class FulfillmentClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FulfillmentClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.fulfillment_service_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.http_timeout_seconds

    async def start_task(
        self,
        task_id: str,
        *,
        station_id: str,
        kds_task_id: str,
        station_worker_id: str,
        started_at: datetime,
    ) -> None:
        await self._post_transition(
            f"/internal/tasks/{task_id}/start",
            {
                "station_id": str(station_id),
                "kds_task_id": str(kds_task_id),
                "station_worker_id": station_worker_id,
                "started_at": started_at.isoformat(),
            },
            rejected_code="fulfillment_start_rejected",
        )

    async def complete_task(
        self,
        task_id: str,
        *,
        station_id: str,
        kds_task_id: str,
        station_worker_id: str,
        completed_at: datetime,
    ) -> None:
        await self._post_transition(
            f"/internal/tasks/{task_id}/complete",
            {
                "station_id": str(station_id),
                "kds_task_id": str(kds_task_id),
                "station_worker_id": station_worker_id,
                "completed_at": completed_at.isoformat(),
            },
            rejected_code="fulfillment_complete_rejected",
        )

    async def _post_transition(self, path: str, payload: dict[str, str], rejected_code: str) -> None:
        headers = self._headers()
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.post(path, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise FulfillmentClientError("fulfillment_service_unavailable") from exc

        if response.status_code == 409:
            raise FulfillmentClientError(rejected_code)
        if response.status_code >= 500:
            raise FulfillmentClientError("fulfillment_service_unavailable")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FulfillmentClientError("fulfillment_service_unavailable") from exc

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        correlation_id = get_correlation_id()
        request_id = get_request_id()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        if request_id:
            headers["X-Request-ID"] = request_id
        return headers


fulfillment_client = FulfillmentClient()


def get_fulfillment_client() -> FulfillmentClient:
    return fulfillment_client
