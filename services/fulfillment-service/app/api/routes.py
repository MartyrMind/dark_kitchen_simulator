from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.kitchen import KitchenServiceClient
from app.clients.menu import MenuServiceClient
from app.config import settings
from app.db import get_session
from app.events.mongo import create_mongo_client
from app.events.task_events import TaskQueuedEventWriter, TaskTransitionEventWriter
from app.redis.client import create_redis_client
from app.redis.streams import RedisTaskPublisher
from app.schemas import (
    CompleteTaskRequest,
    CompleteTaskResponse,
    DispatchFailedRequest,
    DispatchReadinessResponse,
    KitchenTaskRead,
    MarkDisplayedRequest,
    MarkDisplayedResponse,
    OrderCreate,
    OrderCreatedRead,
    OrderRead,
    StartTaskRequest,
    StartTaskResponse,
    TaskSnapshotResponse,
)
from app.services import OrderCreationService, TaskTransitionService
from dk_common.health import build_health_response

router = APIRouter()


def get_kitchen_client() -> KitchenServiceClient:
    return KitchenServiceClient()


def get_menu_client() -> MenuServiceClient:
    return MenuServiceClient()


def get_task_publisher() -> RedisTaskPublisher | None:
    if not settings.redis_publish_enabled:
        return None
    return RedisTaskPublisher(create_redis_client(), settings.redis_task_stream_prefix)


def get_task_event_writer() -> TaskQueuedEventWriter:
    if not settings.mongo_events_enabled:
        return TaskQueuedEventWriter(None, enabled=False)
    return TaskQueuedEventWriter(create_mongo_client())


def get_task_transition_event_writer() -> TaskTransitionEventWriter:
    if not settings.mongo_events_enabled:
        return TaskTransitionEventWriter(None, enabled=False)
    return TaskTransitionEventWriter(create_mongo_client())


def get_order_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    kitchen_client: Annotated[KitchenServiceClient, Depends(get_kitchen_client)],
    menu_client: Annotated[MenuServiceClient, Depends(get_menu_client)],
    task_publisher: Annotated[RedisTaskPublisher | None, Depends(get_task_publisher)],
    task_event_writer: Annotated[TaskQueuedEventWriter, Depends(get_task_event_writer)],
) -> OrderCreationService:
    return OrderCreationService(session, kitchen_client, menu_client, task_publisher, task_event_writer)


def get_task_transition_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    task_event_writer: Annotated[TaskTransitionEventWriter, Depends(get_task_transition_event_writer)],
) -> TaskTransitionService:
    return TaskTransitionService(session, task_event_writer)


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


@router.get("/internal/tasks/{task_id}", response_model=TaskSnapshotResponse)
async def get_task_snapshot(
    task_id: UUID,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.get_snapshot(task_id)


@router.get("/internal/tasks/{task_id}/dispatch-readiness", response_model=DispatchReadinessResponse)
async def get_dispatch_readiness(
    task_id: UUID,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.dispatch_readiness(task_id)


@router.post("/internal/tasks/{task_id}/mark-displayed", response_model=MarkDisplayedResponse)
async def mark_task_displayed(
    task_id: UUID,
    payload: MarkDisplayedRequest,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.mark_displayed(task_id, payload)


@router.post("/internal/tasks/{task_id}/start", response_model=StartTaskResponse)
async def start_task(
    task_id: UUID,
    payload: StartTaskRequest,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.start_task(task_id, payload)


@router.post("/internal/tasks/{task_id}/complete", response_model=CompleteTaskResponse)
async def complete_task(
    task_id: UUID,
    payload: CompleteTaskRequest,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.complete_task(task_id, payload)


@router.post("/internal/tasks/{task_id}/dispatch-failed", response_model=TaskSnapshotResponse)
async def dispatch_failed(
    task_id: UUID,
    payload: DispatchFailedRequest,
    service: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
):
    return await service.dispatch_failed(task_id, payload)
