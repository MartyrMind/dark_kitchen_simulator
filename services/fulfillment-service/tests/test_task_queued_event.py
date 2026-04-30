from app.services import OrderCreationService
from conftest import BURGER_ID, FakeKitchenClient, FakeMenuClient, FakeTaskEventWriter, FakeTaskPublisher, KITCHEN_ID


async def test_task_queued_event_is_written(session):
    from app.schemas import OrderCreate

    event_writer = FakeTaskEventWriter()
    service = OrderCreationService(
        session,
        FakeKitchenClient(),
        FakeMenuClient(),
        FakeTaskPublisher(),
        event_writer,
    )

    await service.create_order(OrderCreate(kitchen_id=KITCHEN_ID, items=[{"menu_item_id": BURGER_ID, "quantity": 1}]))

    task_events = [event for event in event_writer.events if event["event_type"] == "TaskQueued"]
    assert len(task_events) == 2
    assert task_events[0]["task_id"]
    assert task_events[0]["order_id"]
    assert task_events[0]["kitchen_id"] == str(KITCHEN_ID)
    assert task_events[0]["station_type"] == "grill"
    assert task_events[0]["payload"]["stream"]
    assert task_events[0]["payload"]["redis_message_id"]


async def test_mongo_event_failure_does_not_fail_order_creation(session):
    from app.schemas import OrderCreate

    service = OrderCreationService(
        session,
        FakeKitchenClient(),
        FakeMenuClient(),
        FakeTaskPublisher(),
        FakeTaskEventWriter(fail=True),
    )

    created = await service.create_order(
        OrderCreate(kitchen_id=KITCHEN_ID, items=[{"menu_item_id": BURGER_ID, "quantity": 1}])
    )
    tasks = await service.list_order_tasks(created.id)

    assert created.queued_tasks_count == 2
    assert {task.status for task in tasks} == {"queued"}
