from sqlalchemy import select

from app.models import KitchenTask
from app.services import OrderCreationService
from conftest import BURGER_ID, FakeKitchenClient, FakeMenuClient, FakeTaskEventWriter, FakeTaskPublisher, KITCHEN_ID


async def test_redis_failure_leaves_tasks_created(session):
    from app.schemas import OrderCreate

    service = OrderCreationService(
        session,
        FakeKitchenClient(),
        FakeMenuClient(),
        FakeTaskPublisher(fail=True),
        FakeTaskEventWriter(),
    )

    try:
        await service.create_order(OrderCreate(kitchen_id=KITCHEN_ID, items=[{"menu_item_id": BURGER_ID, "quantity": 1}]))
    except Exception as exc:
        assert getattr(exc, "error", "") == "task_publish_failed"
    else:
        raise AssertionError("expected task publish failure")

    result = await session.scalars(select(KitchenTask))
    tasks = list(result)
    assert len(tasks) == 2
    assert {task.status for task in tasks} == {"created"}
    assert {task.attempts for task in tasks} == {0}
    assert {task.redis_message_id for task in tasks} == {None}
