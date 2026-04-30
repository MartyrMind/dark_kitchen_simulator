from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import KitchenTask, Order, OrderItem, TaskDependency
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
