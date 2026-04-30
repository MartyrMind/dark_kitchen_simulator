import pytest

from app.clients.kitchen import KitchenNotActiveError
from app.clients.menu import MenuItemNotAvailableError, RecipeStepsNotFoundError
from app.services import OrderCreationService
from conftest import BURGER_ID, FakeKitchenClient, FakeMenuClient, KITCHEN_ID


def _payload(quantity: int = 2):
    from app.schemas import OrderCreate

    return OrderCreate(kitchen_id=KITCHEN_ID, items=[{"menu_item_id": BURGER_ID, "quantity": quantity}])


async def test_create_order_creates_items_tasks_and_dependencies(session):
    service = OrderCreationService(session, FakeKitchenClient(), FakeMenuClient())

    created = await service.create_order(_payload())
    tasks = await service.list_order_tasks(created.id)

    assert created.status == "created"
    assert created.tasks_count == 4
    assert len(created.items) == 1
    assert created.items[0].quantity == 2
    assert len(tasks) == 4
    assert [task.status for task in tasks] == ["created", "created", "created", "created"]
    assert "queued" not in [task.status for task in tasks]
    assert len([task for task in tasks if task.depends_on_task_ids]) == 2


async def test_create_order_rejects_inactive_kitchen(session):
    service = OrderCreationService(session, FakeKitchenClient(status="inactive"), FakeMenuClient())

    with pytest.raises(KitchenNotActiveError):
        await service.create_order(_payload())


async def test_create_order_rejects_unavailable_menu_item(session):
    service = OrderCreationService(session, FakeKitchenClient(), FakeMenuClient(available=False))

    with pytest.raises(MenuItemNotAvailableError):
        await service.create_order(_payload())


async def test_create_order_rejects_empty_recipe(session):
    service = OrderCreationService(session, FakeKitchenClient(), FakeMenuClient(empty_recipe=True))

    with pytest.raises(RecipeStepsNotFoundError):
        await service.create_order(_payload())
