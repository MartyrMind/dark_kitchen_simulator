from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.statuses import TaskStatus
from app.models import KitchenTask, OrderItem, TaskDependency
from app.schemas import RecipeSnapshot


@dataclass(frozen=True)
class BuiltTasks:
    tasks: list[KitchenTask]
    dependencies: list[TaskDependency]


class TaskBuilder:
    def build(
        self,
        order_id: UUID,
        order_items: list[OrderItem],
        recipes_by_menu_item_id: dict[UUID, RecipeSnapshot],
    ) -> BuiltTasks:
        tasks: list[KitchenTask] = []
        dependencies: list[TaskDependency] = []

        for order_item in order_items:
            recipe = recipes_by_menu_item_id[order_item.menu_item_id]
            steps = sorted(recipe.steps, key=lambda step: step.step_order)

            for unit_index in range(1, order_item.quantity + 1):
                previous_task: KitchenTask | None = None
                for step in steps:
                    task = KitchenTask(
                        id=uuid4(),
                        order_id=order_id,
                        order_item_id=order_item.id,
                        menu_item_id=order_item.menu_item_id,
                        station_type=step.station_type,
                        operation=step.operation,
                        status=TaskStatus.created,
                        estimated_duration_seconds=step.duration_seconds,
                        attempts=0,
                        recipe_step_order=step.step_order,
                        item_unit_index=unit_index,
                    )
                    tasks.append(task)
                    if previous_task is not None:
                        dependencies.append(
                            TaskDependency(task_id=task.id, depends_on_task_id=previous_task.id)
                        )
                    previous_task = task

        return BuiltTasks(tasks=tasks, dependencies=dependencies)
