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


class TaskTransitionEventWriter:
    def __init__(
        self,
        mongo_client: AsyncIOMotorClient | None,
        database_name: str = settings.mongo_database,
        enabled: bool = settings.mongo_events_enabled,
    ) -> None:
        self.mongo_client = mongo_client
        self.database_name = database_name
        self.enabled = enabled

    async def write_task_displayed(self, task: KitchenTask, dispatcher_id: str) -> None:
        await self._write_task_event(
            "TaskDisplayed",
            task,
            {
                "dispatcher_id": dispatcher_id,
            },
            created_at=task.displayed_at,
        )

    async def write_task_started(self, task: KitchenTask, station_worker_id: str) -> None:
        await self._write_task_event(
            "TaskStarted",
            task,
            {
                "station_worker_id": station_worker_id,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "sla_deadline_at": task.sla_deadline_at.isoformat() if task.sla_deadline_at else None,
            },
            created_at=task.started_at,
        )

    async def write_task_completed(self, task: KitchenTask, station_worker_id: str) -> None:
        await self._write_task_event(
            "TaskCompleted",
            task,
            {
                "station_worker_id": station_worker_id,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "actual_duration_seconds": task.actual_duration_seconds,
                "delay_seconds": task.delay_seconds,
            },
            created_at=task.completed_at,
        )

    async def write_task_dispatch_failed(self, task: KitchenTask, reason: str, dispatcher_id: str) -> None:
        await self._write_task_event(
            "TaskDispatchFailed",
            task,
            {
                "reason": reason,
                "dispatcher_id": dispatcher_id,
                "attempts": task.attempts,
            },
        )

    async def write_order_ready_for_pickup(self, order: Order, completed_tasks_count: int) -> None:
        if not self.enabled or self.mongo_client is None:
            return
        event = {
            "event_type": "OrderReadyForPickup",
            "order_id": str(order.id),
            "kitchen_id": str(order.kitchen_id),
            "payload": {"completed_tasks_count": completed_tasks_count},
            "correlation_id": get_correlation_id(),
            "service": settings.service_name,
            "created_at": datetime.now(UTC).isoformat(),
        }
        try:
            await self.mongo_client[self.database_name]["order_events"].insert_one(event)
        except Exception:
            logger.exception("mongo_event_write_failed", extra={"order_id": str(order.id)})

    async def _write_task_event(
        self,
        event_type: str,
        task: KitchenTask,
        payload: dict,
        created_at: datetime | None = None,
    ) -> None:
        if not self.enabled or self.mongo_client is None:
            return
        event = {
            "event_type": event_type,
            "task_id": str(task.id),
            "order_id": str(task.order_id),
            "kitchen_id": str(task.order.kitchen_id),
            "station_type": task.station_type,
            "station_id": str(task.station_id) if task.station_id else None,
            "kds_task_id": str(task.kds_task_id) if task.kds_task_id else None,
            "payload": payload,
            "correlation_id": get_correlation_id(),
            "service": settings.service_name,
            "created_at": (created_at or datetime.now(UTC)).isoformat(),
        }
        try:
            await self.mongo_client[self.database_name]["task_events"].insert_one(event)
        except Exception:
            logger.exception("mongo_event_write_failed", extra={"task_id": str(task.id)})
