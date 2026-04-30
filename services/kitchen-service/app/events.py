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

    def _get_client(self) -> Any:
        if self._client is None:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._client = AsyncIOMotorClient(settings.mongo_url)
        return self._client


event_writer = MongoKdsEventWriter()


def get_event_writer() -> MongoKdsEventWriter:
    return event_writer
