from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis

from app.config import settings
from app.domain.errors import TaskPublishFailedError
from app.models import KitchenTask, Order
from dk_common.correlation import get_correlation_id


def build_task_stream_name(
    kitchen_id: UUID | str,
    station_type: str,
    stream_prefix: str = settings.redis_task_stream_prefix,
) -> str:
    return f"{stream_prefix}:{kitchen_id}:station:{station_type}"


def _serialize_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def build_redis_task_message(
    task: KitchenTask,
    order: Order,
    menu_item_name: str | None,
    correlation_id: str | None = None,
) -> dict[str, str]:
    fields = {
        "task_id": str(task.id),
        "order_id": str(task.order_id),
        "kitchen_id": str(order.kitchen_id),
        "station_type": task.station_type,
        "operation": task.operation,
        "menu_item_id": str(task.menu_item_id),
        "menu_item_name": menu_item_name or "",
        "estimated_duration_seconds": str(task.estimated_duration_seconds),
        "pickup_deadline": _serialize_datetime(order.pickup_deadline),
        "attempt": "1",
        "created_at": _serialize_datetime(task.created_at),
        "recipe_step_order": str(task.recipe_step_order),
        "item_unit_index": str(task.item_unit_index),
    }
    if correlation_id:
        fields["correlation_id"] = correlation_id
    return fields


class RedisTaskPublisher:
    def __init__(self, redis: Redis, stream_prefix: str = settings.redis_task_stream_prefix) -> None:
        self.redis = redis
        self.stream_prefix = stream_prefix

    async def publish_task(self, task: KitchenTask, order: Order, menu_item_name: str | None) -> tuple[str, str]:
        stream_name = build_task_stream_name(order.kitchen_id, task.station_type, self.stream_prefix)
        message = build_redis_task_message(task, order, menu_item_name, get_correlation_id())
        try:
            redis_message_id = await self.redis.xadd(stream_name, message)
        except Exception as exc:
            raise TaskPublishFailedError() from exc
        return stream_name, str(redis_message_id)
