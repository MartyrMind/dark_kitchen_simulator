from uuid import UUID
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import KitchenTask, Order, OrderItem, TaskDependency
from app.domain.statuses import TaskStatus
from app.schemas import OrderCreate


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_order(self, payload: OrderCreate) -> Order:
        order = Order(kitchen_id=payload.kitchen_id, pickup_deadline=payload.pickup_deadline)
        self.session.add(order)
        await self.session.flush()
        return order

    async def create_order_item(self, order_id: UUID, menu_item_id: UUID, quantity: int) -> OrderItem:
        item = OrderItem(order_id=order_id, menu_item_id=menu_item_id, quantity=quantity)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_order(self, order_id: UUID) -> Order | None:
        result = await self.session.scalars(
            select(Order).where(Order.id == order_id).options(selectinload(Order.items))
        )
        return result.first()

    async def get_order_for_update(self, order_id: UUID) -> Order | None:
        return await self.session.scalar(select(Order).where(Order.id == order_id).with_for_update())


class KitchenTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_tasks(self, tasks: list[KitchenTask], dependencies: list[TaskDependency]) -> None:
        self.session.add_all(tasks)
        await self.session.flush()
        self.session.add_all(dependencies)
        await self.session.flush()

    async def list_by_order(self, order_id: UUID) -> list[KitchenTask]:
        result = await self.session.scalars(
            select(KitchenTask)
            .where(KitchenTask.order_id == order_id)
            .options(selectinload(KitchenTask.dependencies))
            .order_by(KitchenTask.order_item_id, KitchenTask.item_unit_index, KitchenTask.recipe_step_order)
        )
        return list(result)

    async def mark_tasks_queued(self, published_tasks: list[tuple[KitchenTask, str, str]]) -> None:
        queued_at = datetime.now(UTC)
        for task, stream, redis_message_id in published_tasks:
            task.status = TaskStatus.queued
            task.attempts = 1
            task.queued_at = queued_at
            task.redis_stream = stream
            task.redis_message_id = redis_message_id
        await self.session.flush()

    async def get(self, task_id: UUID) -> KitchenTask | None:
        return await self.session.scalar(
            select(KitchenTask).where(KitchenTask.id == task_id).options(selectinload(KitchenTask.order))
        )

    async def get_for_update(self, task_id: UUID) -> KitchenTask | None:
        return await self.session.scalar(
            select(KitchenTask)
            .where(KitchenTask.id == task_id)
            .options(selectinload(KitchenTask.order))
            .with_for_update()
        )

    async def unfinished_dependencies(self, task_id: UUID) -> list[UUID]:
        result = await self.session.scalars(
            select(TaskDependency.depends_on_task_id)
            .join(KitchenTask, KitchenTask.id == TaskDependency.depends_on_task_id)
            .where(TaskDependency.task_id == task_id, KitchenTask.status != TaskStatus.done)
            .order_by(TaskDependency.depends_on_task_id)
        )
        return list(result)

    async def all_order_tasks_done(self, order_id: UUID) -> bool:
        unfinished_count = await self.session.scalar(
            select(func.count(KitchenTask.id)).where(
                KitchenTask.order_id == order_id,
                KitchenTask.status != TaskStatus.done,
            )
        )
        return int(unfinished_count or 0) == 0

    async def completed_order_tasks_count(self, order_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count(KitchenTask.id)).where(
                KitchenTask.order_id == order_id,
                KitchenTask.status == TaskStatus.done,
            )
        )
        return int(count or 0)
