from datetime import UTC, datetime
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models import KitchenTask, Order
from dk_common.correlation import get_correlation_id

logger = logging.getLogger(__name__)


class TaskQueuedEventWriter:
    def __init__(
        self,
        mongo_client: AsyncIOMotorClient | None,
        database_name: str = settings.mongo_database,
        enabled: bool = settings.mongo_events_enabled,
    ) -> None:
        self.mongo_client = mongo_client
        self.database_name = database_name
        self.enabled = enabled

    async def write_task_queued(
        self,
        task: KitchenTask,
        order: Order,
        stream: str,
        redis_message_id: str,
    ) -> None:
        if not self.enabled or self.mongo_client is None:
            return

        event = {
            "event_type": "TaskQueued",
            "task_id": str(task.id),
            "order_id": str(task.order_id),
            "kitchen_id": str(order.kitchen_id),
            "station_type": task.station_type,
            "payload": {
                "stream": stream,
                "redis_message_id": redis_message_id,
                "operation": task.operation,
                "estimated_duration_seconds": task.estimated_duration_seconds,
            },
            "correlation_id": get_correlation_id(),
            "service": settings.service_name,
            "created_at": datetime.now(UTC).isoformat(),
        }
        try:
            await self.mongo_client[self.database_name]["task_events"].insert_one(event)
        except Exception:
            logger.exception("mongo_event_write_failed", extra={"task_id": str(task.id)})
