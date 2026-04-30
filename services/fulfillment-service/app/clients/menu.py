from uuid import UUID

import httpx

from app.clients.base import correlation_headers
from app.config import settings
from app.domain.errors import ConflictError, ExternalServiceUnavailableError, NotFoundError
from app.schemas import KitchenMenuItemSnapshot, RecipeSnapshot


class MenuItemNotFoundError(NotFoundError):
    error = "menu_item_not_found"
    message = "Menu item not found"


class MenuItemNotAvailableError(ConflictError):
    error = "menu_item_not_available"
    message = "Menu item is not available for this kitchen"


class RecipeStepsNotFoundError(ConflictError):
    error = "recipe_steps_not_found"
    message = "Menu item has no recipe steps"


class MenuServiceUnavailableError(ExternalServiceUnavailableError):
    error = "menu_service_unavailable"
    message = "Menu Service is unavailable"


class MenuServiceClient:
    def __init__(
        self,
        base_url: str = settings.menu_service_url,
        timeout_seconds: float = settings.http_timeout_seconds,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def get_kitchen_menu(self, kitchen_id: UUID) -> list[KitchenMenuItemSnapshot]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.get(f"/kitchens/{kitchen_id}/menu", headers=correlation_headers())
        except httpx.HTTPError as exc:
            raise MenuServiceUnavailableError() from exc

        if response.status_code >= 500:
            raise MenuServiceUnavailableError()
        try:
            response.raise_for_status()
            return [KitchenMenuItemSnapshot.model_validate(item) for item in response.json()]
        except (httpx.HTTPError, ValueError) as exc:
            raise MenuServiceUnavailableError() from exc

    async def get_recipe(self, menu_item_id: UUID) -> RecipeSnapshot:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.get(f"/menu-items/{menu_item_id}/recipe", headers=correlation_headers())
        except httpx.HTTPError as exc:
            raise MenuServiceUnavailableError() from exc

        if response.status_code == 404:
            raise MenuItemNotFoundError()
        if response.status_code >= 500:
            raise MenuServiceUnavailableError()
        try:
            response.raise_for_status()
            recipe = RecipeSnapshot.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise MenuServiceUnavailableError() from exc
        if not recipe.steps:
            raise RecipeStepsNotFoundError()
        return recipe
