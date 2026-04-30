from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.config import settings
from app.models import KdsStationTask


class MongoKdsEventWriter:
    def __init__(self) -> None:
        self._client: Any | None = None

    async def write_task_displayed(
        self,
        task: KdsStationTask,
        correlation_id: str | None,
    ) -> None:
        if not settings.mongo_events_enabled:
            return

        event = {
            "event_type": "KdsTaskDisplayed",
            "task_id": task.task_id,
            "order_id": task.order_id,
            "kitchen_id": task.kitchen_id,
            "station_id": task.station_id,
            "station_type": str(task.station_type),
            "kds_task_id": task.id,
            "payload": {
                "operation": task.operation,
                "menu_item_name": task.menu_item_name,
                "estimated_duration_seconds": task.estimated_duration_seconds,
                "idempotency_key": task.idempotency_key,
            },
            "correlation_id": correlation_id,
            "service": settings.service_name,
            "created_at": datetime.now(UTC),
        }

        try:
            client = self._get_client()
            await client[settings.mongo_database]["kds_events"].insert_one(event)
        except Exception as exc:
            logger.bind(
                event="kds_task_displayed_event_failed",
                task_id=task.task_id,
                station_id=task.station_id,
            ).error("failed to write KdsTaskDisplayed event: {}", exc)

    async def write_kds_event(
        self,
        event_type: str,
        task: KdsStationTask,
        station_worker_id: str,
        correlation_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        if not settings.mongo_events_enabled:
            return

        event = {
            "event_type": event_type,
            "task_id": task.task_id,
            "kds_task_id": task.id,
            "order_id": task.order_id,
            "kitchen_id": task.kitchen_id,
            "station_id": task.station_id,
            "station_type": str(task.station_type),
            "station_worker_id": station_worker_id,
            "payload": payload,
            "correlation_id": correlation_id,
            "service": settings.service_name,
            "created_at": datetime.now(UTC),
        }
        await self._safe_insert("kds_events", event, event_type, task.task_id, task.station_id)

    async def write_station_event(
        self,
        event_type: str,
        *,
        kitchen_id: int,
        station_id: int,
        correlation_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        if not settings.mongo_events_enabled:
            return

        event = {
            "event_type": event_type,
            "kitchen_id": kitchen_id,
            "station_id": station_id,
            "payload": payload,
            "correlation_id": correlation_id,
            "service": settings.service_name,
            "created_at": datetime.now(UTC),
        }
        await self._safe_insert("station_events", event, event_type, None, station_id)

    async def _safe_insert(
        self,
        collection: str,
        event: dict[str, Any],
        event_type: str,
        task_id: str | None,
        station_id: int,
    ) -> None:
        try:
            client = self._get_client()
            await client[settings.mongo_database][collection].insert_one(event)
        except Exception as exc:
            logger.bind(
                event=f"{event_type}_event_failed",
                task_id=task_id,
                station_id=station_id,
            ).error("failed to write {} event: {}", event_type, exc)

    def _get_client(self) -> Any:
        if self._client is None:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._client = AsyncIOMotorClient(settings.mongo_url)
        return self._client


event_writer = MongoKdsEventWriter()


def get_event_writer() -> MongoKdsEventWriter:
    return event_writer
