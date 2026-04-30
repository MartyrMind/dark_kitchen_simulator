from uuid import UUID

import httpx

from app.clients.base import correlation_headers
from app.config import settings
from app.domain.errors import ConflictError, ExternalServiceUnavailableError, NotFoundError
from app.schemas import KitchenSnapshot


class KitchenNotFoundError(NotFoundError):
    error = "kitchen_not_found"
    message = "Kitchen not found"


class KitchenNotActiveError(ConflictError):
    error = "kitchen_not_active"
    message = "Kitchen is not active"


class KitchenServiceUnavailableError(ExternalServiceUnavailableError):
    error = "kitchen_service_unavailable"
    message = "Kitchen Service is unavailable"


class KitchenServiceClient:
    def __init__(
        self,
        base_url: str = settings.kitchen_service_url,
        timeout_seconds: float = settings.http_timeout_seconds,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def get_kitchen(self, kitchen_id: UUID) -> KitchenSnapshot:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.get(f"/kitchens/{kitchen_id}", headers=correlation_headers())
        except httpx.HTTPError as exc:
            raise KitchenServiceUnavailableError() from exc

        if response.status_code == 404:
            raise KitchenNotFoundError()
        if response.status_code >= 500:
            raise KitchenServiceUnavailableError()
        try:
            response.raise_for_status()
            kitchen = KitchenSnapshot.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise KitchenServiceUnavailableError() from exc
        if kitchen.status != "active":
            raise KitchenNotActiveError()
        return kitchen
