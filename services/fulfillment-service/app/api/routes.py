from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.kitchen import KitchenServiceClient
from app.clients.menu import MenuServiceClient
from app.config import settings
from app.db import get_session
from app.schemas import KitchenTaskRead, OrderCreate, OrderCreatedRead, OrderRead
from app.services import OrderCreationService
from dk_common.health import build_health_response

router = APIRouter()


def get_kitchen_client() -> KitchenServiceClient:
    return KitchenServiceClient()


def get_menu_client() -> MenuServiceClient:
    return MenuServiceClient()


def get_order_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    kitchen_client: Annotated[KitchenServiceClient, Depends(get_kitchen_client)],
    menu_client: Annotated[MenuServiceClient, Depends(get_menu_client)],
) -> OrderCreationService:
    return OrderCreationService(session, kitchen_client, menu_client)


@router.get("/health")
async def health() -> dict[str, str | None]:
    return build_health_response(
        service_name=settings.service_name,
        environment=settings.environment,
        version=settings.version,
    )


@router.post("/orders", response_model=OrderCreatedRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    service: Annotated[OrderCreationService, Depends(get_order_service)],
):
    return await service.create_order(payload)


@router.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: UUID,
    service: Annotated[OrderCreationService, Depends(get_order_service)],
):
    return await service.get_order_read(order_id)


@router.get("/orders/{order_id}/tasks", response_model=list[KitchenTaskRead])
async def list_order_tasks(
    order_id: UUID,
    service: Annotated[OrderCreationService, Depends(get_order_service)],
):
    return await service.list_order_tasks(order_id)
