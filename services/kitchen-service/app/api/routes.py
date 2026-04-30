from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import StationType
from app.schemas import (
    KitchenCreate,
    KitchenRead,
    StationCapacityUpdate,
    StationCreate,
    StationRead,
    StationStatusUpdate,
)
from app.services import KitchenService
from dk_common.health import build_health_response

router = APIRouter()


def get_kitchen_service(session: Annotated[AsyncSession, Depends(get_session)]) -> KitchenService:
    return KitchenService(session)


@router.get("/health")
async def health() -> dict[str, str | None]:
    return build_health_response(
        service_name=settings.service_name,
        environment=settings.environment,
        version=settings.version,
    )


@router.post("/kitchens", response_model=KitchenRead, status_code=status.HTTP_201_CREATED)
async def create_kitchen(
    payload: KitchenCreate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.create_kitchen(payload)


@router.get("/kitchens", response_model=list[KitchenRead])
async def list_kitchens(service: Annotated[KitchenService, Depends(get_kitchen_service)]):
    return await service.list_kitchens()


@router.get("/kitchens/{kitchen_id}", response_model=KitchenRead)
async def get_kitchen(
    kitchen_id: int,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.get_kitchen(kitchen_id)


@router.post(
    "/kitchens/{kitchen_id}/stations",
    response_model=StationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_station(
    kitchen_id: int,
    payload: StationCreate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.create_station(kitchen_id, payload)


@router.get("/kitchens/{kitchen_id}/stations", response_model=list[StationRead])
async def list_stations(
    kitchen_id: int,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
    station_type: StationType | None = Query(default=None),
):
    return await service.list_stations(kitchen_id, station_type)


@router.patch("/stations/{station_id}/capacity", response_model=StationRead)
async def update_station_capacity(
    station_id: int,
    payload: StationCapacityUpdate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.update_station_capacity(station_id, payload.capacity)


@router.patch("/stations/{station_id}/status", response_model=StationRead)
async def update_station_status(
    station_id: int,
    payload: StationStatusUpdate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.update_station_status(station_id, payload.status)
