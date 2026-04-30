from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.clients import FulfillmentClient, get_fulfillment_client
from app.db import get_session
from app.events import MongoKdsEventWriter, get_event_writer
from app.models import KdsStationTask, KdsTaskStatus, StationType
from app.schemas import (
    DispatchCandidateResponse,
    KitchenCreate,
    KitchenRead,
    KdsTaskClaimRequest,
    KdsTaskClaimResponse,
    KdsTaskCompleteRequest,
    KdsTaskCompleteResponse,
    KdsStationTaskResponse,
    KdsTaskDeliveryRequest,
    KdsTaskDeliveryResponse,
    StationCapacityUpdate,
    StationCreate,
    StationRead,
    StationStatusUpdate,
)
from app.services import KdsDomainError, KdsService, KitchenService, NotFoundError
from dk_common.correlation import get_correlation_id
from dk_common.health import build_health_response

router = APIRouter()


def parse_uuid(value: str, code: str = "not_found") -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise NotFoundError(code) from exc


def parse_kds_station_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise KdsDomainError("station_not_found", "Station not found", status_code=404) from exc


def get_kitchen_service(session: Annotated[AsyncSession, Depends(get_session)]) -> KitchenService:
    return KitchenService(session, get_event_writer())


def get_kds_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    event_writer: Annotated[MongoKdsEventWriter, Depends(get_event_writer)],
    fulfillment_client: Annotated[FulfillmentClient, Depends(get_fulfillment_client)],
) -> KdsService:
    return KdsService(session, event_writer, fulfillment_client)


def kds_task_delivery_response(task: KdsStationTask) -> KdsTaskDeliveryResponse:
    return KdsTaskDeliveryResponse(
        kds_task_id=task.id,
        task_id=task.task_id,
        station_id=task.station_id,
        status=task.status,
    )


def kds_station_task_response(task: KdsStationTask) -> KdsStationTaskResponse:
    return KdsStationTaskResponse(
        kds_task_id=task.id,
        task_id=task.task_id,
        order_id=task.order_id,
        station_id=task.station_id,
        operation=task.operation,
        menu_item_name=task.menu_item_name,
        status=task.status,
        estimated_duration_seconds=task.estimated_duration_seconds,
        pickup_deadline=task.pickup_deadline,
        displayed_at=task.displayed_at,
    )


def kds_task_claim_response(task: KdsStationTask) -> KdsTaskClaimResponse:
    return KdsTaskClaimResponse(
        kds_task_id=task.id,
        task_id=task.task_id,
        station_id=task.station_id,
        status=task.status,
        claimed_by=task.claimed_by or "",
        claimed_at=task.claimed_at,
    )


def kds_task_complete_response(task: KdsStationTask) -> KdsTaskCompleteResponse:
    return KdsTaskCompleteResponse(
        kds_task_id=task.id,
        task_id=task.task_id,
        station_id=task.station_id,
        status=task.status,
        claimed_by=task.claimed_by or "",
        completed_at=task.completed_at,
    )


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
    kitchen_id: str,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.get_kitchen(parse_uuid(kitchen_id, "kitchen_not_found"))


@router.post(
    "/kitchens/{kitchen_id}/stations",
    response_model=StationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_station(
    kitchen_id: str,
    payload: StationCreate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.create_station(parse_uuid(kitchen_id, "kitchen_not_found"), payload)


@router.get("/kitchens/{kitchen_id}/stations", response_model=list[StationRead])
async def list_stations(
    kitchen_id: str,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
    station_type: StationType | None = Query(default=None),
):
    return await service.list_stations(parse_uuid(kitchen_id, "kitchen_not_found"), station_type)


@router.patch("/stations/{station_id}/capacity", response_model=StationRead)
async def update_station_capacity(
    station_id: str,
    payload: StationCapacityUpdate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.update_station_capacity(parse_uuid(station_id, "station_not_found"), payload.capacity)


@router.patch("/stations/{station_id}/status", response_model=StationRead)
async def update_station_status(
    station_id: str,
    payload: StationStatusUpdate,
    service: Annotated[KitchenService, Depends(get_kitchen_service)],
):
    return await service.update_station_status(parse_uuid(station_id, "station_not_found"), payload.status)


@router.get("/internal/kds/dispatch-candidates", response_model=list[DispatchCandidateResponse])
async def dispatch_candidates(
    kitchen_id: str,
    station_type: StationType,
    service: Annotated[KdsService, Depends(get_kds_service)],
):
    return await service.dispatch_candidates(parse_uuid(kitchen_id, "kitchen_not_found"), station_type)


@router.post(
    "/internal/kds/stations/{station_id}/tasks",
    response_model=KdsTaskDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def deliver_kds_task(
    station_id: str,
    payload: KdsTaskDeliveryRequest,
    response: Response,
    service: Annotated[KdsService, Depends(get_kds_service)],
):
    task, created = await service.deliver_task(parse_kds_station_uuid(station_id), payload, get_correlation_id())
    if not created:
        response.status_code = status.HTTP_200_OK
    return kds_task_delivery_response(task)


@router.get("/kds/stations/{station_id}/tasks", response_model=list[KdsStationTaskResponse])
async def list_kds_station_tasks(
    station_id: str,
    service: Annotated[KdsService, Depends(get_kds_service)],
    task_status: KdsTaskStatus = Query(default=KdsTaskStatus.displayed, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    tasks = await service.list_station_tasks(parse_kds_station_uuid(station_id), task_status, limit, offset)
    return [kds_station_task_response(task) for task in tasks]


@router.post("/kds/stations/{station_id}/tasks/{task_id}/claim", response_model=KdsTaskClaimResponse)
async def claim_kds_task(
    station_id: str,
    task_id: str,
    payload: KdsTaskClaimRequest,
    service: Annotated[KdsService, Depends(get_kds_service)],
):
    task = await service.claim_task(parse_kds_station_uuid(station_id), task_id, payload, get_correlation_id())
    return kds_task_claim_response(task)


@router.post("/kds/stations/{station_id}/tasks/{task_id}/complete", response_model=KdsTaskCompleteResponse)
async def complete_kds_task(
    station_id: str,
    task_id: str,
    payload: KdsTaskCompleteRequest,
    service: Annotated[KdsService, Depends(get_kds_service)],
):
    task = await service.complete_task(parse_kds_station_uuid(station_id), task_id, payload, get_correlation_id())
    return kds_task_complete_response(task)
