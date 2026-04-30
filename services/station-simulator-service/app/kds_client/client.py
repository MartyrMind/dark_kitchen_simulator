from __future__ import annotations

from uuid import uuid4

import httpx

from app.kds_client.schemas import (
    ClaimConflict,
    ClaimResponse,
    CompleteResponse,
    KdsClientError,
    KdsTask,
    RetryableKdsError,
)


class KdsClient:
    def __init__(self, base_url: str, timeout_seconds: float = 3.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_station_tasks(self, station_id: int | str, correlation_id: str | None = None) -> list[KdsTask]:
        try:
            response = await self._client.get(
                f"/kds/stations/{station_id}/tasks",
                headers=self._correlation_headers(correlation_id),
            )
        except httpx.TimeoutException as exc:
            raise RetryableKdsError("kds_timeout") from exc
        except httpx.HTTPError as exc:
            raise RetryableKdsError("kds_unavailable") from exc

        self._raise_for_retryable(response)
        if response.status_code >= 400:
            raise KdsClientError(self._error_reason(response))
        return [KdsTask.model_validate(item) for item in response.json()]

    async def claim_task(
        self,
        station_id: int | str,
        task_id: str,
        worker_id: str,
        correlation_id: str | None = None,
    ) -> ClaimResponse:
        try:
            response = await self._client.post(
                f"/kds/stations/{station_id}/tasks/{task_id}/claim",
                json={"station_worker_id": worker_id},
                headers=self._correlation_headers(correlation_id),
            )
        except httpx.TimeoutException as exc:
            raise RetryableKdsError("kds_timeout") from exc
        except httpx.HTTPError as exc:
            raise RetryableKdsError("kds_unavailable") from exc

        if response.status_code == 409:
            raise ClaimConflict(self._error_reason(response))
        self._raise_for_retryable(response)
        if response.status_code >= 400:
            raise KdsClientError(self._error_reason(response))
        return ClaimResponse.model_validate(response.json())

    async def complete_task(
        self,
        station_id: int | str,
        task_id: str,
        worker_id: str,
        correlation_id: str | None = None,
    ) -> CompleteResponse:
        try:
            response = await self._client.post(
                f"/kds/stations/{station_id}/tasks/{task_id}/complete",
                json={"station_worker_id": worker_id},
                headers=self._correlation_headers(correlation_id),
            )
        except httpx.TimeoutException as exc:
            raise RetryableKdsError("kds_timeout") from exc
        except httpx.HTTPError as exc:
            raise RetryableKdsError("kds_unavailable") from exc

        self._raise_for_retryable(response)
        if response.status_code >= 400:
            raise KdsClientError(self._error_reason(response))
        return CompleteResponse.model_validate(response.json())

    def _correlation_headers(self, correlation_id: str | None) -> dict[str, str]:
        correlation_id = correlation_id or str(uuid4())
        return {
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": str(uuid4()),
        }

    def _raise_for_retryable(self, response: httpx.Response) -> None:
        if response.status_code >= 500:
            raise RetryableKdsError(self._error_reason(response))

    def _error_reason(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"http_{response.status_code}"
        return str(payload.get("error") or payload.get("detail") or payload.get("message") or f"http_{response.status_code}")
