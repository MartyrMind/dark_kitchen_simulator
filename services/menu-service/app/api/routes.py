from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import MenuItemStatus
from app.schemas import (
    AvailabilityRead,
    AvailabilityUpsert,
    KitchenMenuItemRead,
    MenuItemCreate,
    MenuItemRead,
    RecipeRead,
    RecipeStepCreate,
    RecipeStepRead,
)
from app.services import MenuService
from dk_common.health import build_health_response

router = APIRouter()


def get_menu_service(session: Annotated[AsyncSession, Depends(get_session)]) -> MenuService:
    return MenuService(session)


@router.get("/health")
async def health() -> dict[str, str | None]:
    return build_health_response(
        service_name=settings.service_name,
        environment=settings.environment,
        version=settings.version,
    )


@router.post("/menu-items", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    payload: MenuItemCreate,
    service: Annotated[MenuService, Depends(get_menu_service)],
):
    return await service.create_menu_item(payload)


@router.get("/menu-items", response_model=list[MenuItemRead])
async def list_menu_items(
    service: Annotated[MenuService, Depends(get_menu_service)],
    status: MenuItemStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await service.list_menu_items(status=status, limit=limit, offset=offset)


@router.get("/menu-items/{menu_item_id}", response_model=MenuItemRead)
async def get_menu_item(
    menu_item_id: UUID,
    service: Annotated[MenuService, Depends(get_menu_service)],
):
    return await service.get_menu_item(menu_item_id)


@router.post(
    "/menu-items/{menu_item_id}/recipe-steps",
    response_model=RecipeStepRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_recipe_step(
    menu_item_id: UUID,
    payload: RecipeStepCreate,
    service: Annotated[MenuService, Depends(get_menu_service)],
):
    return await service.create_recipe_step(menu_item_id, payload)


@router.get("/menu-items/{menu_item_id}/recipe", response_model=RecipeRead)
async def get_recipe(
    menu_item_id: UUID,
    service: Annotated[MenuService, Depends(get_menu_service)],
):
    return await service.get_recipe(menu_item_id)


@router.post(
    "/kitchens/{kitchen_id}/menu-items/{menu_item_id}/availability",
    response_model=AvailabilityRead,
)
async def upsert_availability(
    kitchen_id: UUID,
    menu_item_id: UUID,
    payload: AvailabilityUpsert,
    service: Annotated[MenuService, Depends(get_menu_service)],
):
    return await service.upsert_availability(kitchen_id, menu_item_id, payload)


@router.get("/kitchens/{kitchen_id}/menu", response_model=list[KitchenMenuItemRead])
async def list_kitchen_menu(
    kitchen_id: UUID,
    service: Annotated[MenuService, Depends(get_menu_service)],
    include_unavailable: bool = Query(default=False),
):
    items = await service.list_kitchen_menu(kitchen_id, include_unavailable=include_unavailable)
    return [
        KitchenMenuItemRead(
            id=item.id,
            name=item.name,
            description=item.description,
            status=item.status,
            is_available=item.availability[0].is_available,
        )
        for item in items
    ]
