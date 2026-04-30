from uuid import uuid4

from app.models import OrderItem
from app.schemas import RecipeSnapshot, RecipeStepSnapshot
from app.task_builder import TaskBuilder


def _recipe(*steps):
    return RecipeSnapshot(
        menu_item_id=steps[0][0],
        steps=[
            RecipeStepSnapshot(
                station_type=station_type,
                operation=operation,
                duration_seconds=duration,
                step_order=step_order,
            )
            for _, station_type, operation, duration, step_order in steps
        ],
    )


def _order_item(menu_item_id, quantity):
    return OrderItem(id=uuid4(), order_id=uuid4(), menu_item_id=menu_item_id, quantity=quantity)


def test_builds_two_step_chain_for_one_unit():
    menu_item_id = uuid4()
    order_id = uuid4()
    order_item = _order_item(menu_item_id, 1)
    recipe = _recipe(
        (menu_item_id, "grill", "cook_patty", 480, 1),
        (menu_item_id, "packaging", "pack_burger", 60, 2),
    )

    built = TaskBuilder().build(order_id, [order_item], {menu_item_id: recipe})

    assert len(built.tasks) == 2
    assert len(built.dependencies) == 1
    assert built.dependencies[0].task_id == built.tasks[1].id
    assert built.dependencies[0].depends_on_task_id == built.tasks[0].id


def test_builds_independent_chains_for_quantity_two():
    menu_item_id = uuid4()
    order_id = uuid4()
    order_item = _order_item(menu_item_id, 2)
    recipe = _recipe(
        (menu_item_id, "grill", "cook_patty", 480, 1),
        (menu_item_id, "packaging", "pack_burger", 60, 2),
    )

    built = TaskBuilder().build(order_id, [order_item], {menu_item_id: recipe})

    assert len(built.tasks) == 4
    assert len(built.dependencies) == 2
    assert {task.item_unit_index for task in built.tasks} == {1, 2}
    for dependency in built.dependencies:
        current = next(task for task in built.tasks if task.id == dependency.task_id)
        previous = next(task for task in built.tasks if task.id == dependency.depends_on_task_id)
        assert current.item_unit_index == previous.item_unit_index


def test_sorts_unordered_recipe_steps():
    menu_item_id = uuid4()
    order_id = uuid4()
    order_item = _order_item(menu_item_id, 1)
    recipe = _recipe(
        (menu_item_id, "packaging", "pack_burger", 60, 2),
        (menu_item_id, "grill", "cook_patty", 480, 1),
    )

    built = TaskBuilder().build(order_id, [order_item], {menu_item_id: recipe})

    assert [task.recipe_step_order for task in built.tasks] == [1, 2]
    assert built.dependencies[0].depends_on_task_id == built.tasks[0].id
