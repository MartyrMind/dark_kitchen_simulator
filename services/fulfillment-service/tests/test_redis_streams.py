from datetime import UTC, datetime
from uuid import uuid4

from app.models import KitchenTask, Order
from app.redis.streams import build_redis_task_message, build_task_stream_name


def test_build_task_stream_name():
    kitchen_id = uuid4()

    assert build_task_stream_name(kitchen_id, "grill") == f"stream:kitchen:{kitchen_id}:station:grill"


def test_build_redis_task_message_serializes_required_fields():
    order_id = uuid4()
    kitchen_id = uuid4()
    menu_item_id = uuid4()
    task_id = uuid4()
    pickup_deadline = datetime(2026, 4, 30, 18, 45, tzinfo=UTC)
    created_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)
    order = Order(id=order_id, kitchen_id=kitchen_id, pickup_deadline=pickup_deadline)
    task = KitchenTask(
        id=task_id,
        order_id=order_id,
        order_item_id=uuid4(),
        menu_item_id=menu_item_id,
        station_type="grill",
        operation="cook_patty",
        estimated_duration_seconds=480,
        attempts=0,
        recipe_step_order=1,
        item_unit_index=1,
        created_at=created_at,
    )

    message = build_redis_task_message(task, order, "Burger", "corr-1")

    assert message["task_id"] == str(task_id)
    assert message["order_id"] == str(order_id)
    assert message["kitchen_id"] == str(kitchen_id)
    assert message["menu_item_id"] == str(menu_item_id)
    assert message["menu_item_name"] == "Burger"
    assert message["estimated_duration_seconds"] == "480"
    assert message["pickup_deadline"] == pickup_deadline.isoformat()
    assert message["attempt"] == "1"
    assert message["correlation_id"] == "corr-1"
