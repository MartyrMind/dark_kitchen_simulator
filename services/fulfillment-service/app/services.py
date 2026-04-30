from uuid import UUID
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.kitchen import KitchenServiceClient
from app.clients.menu import (
    MenuItemNotAvailableError,
    MenuServiceClient,
    RecipeStepsNotFoundError,
)
from app.domain.errors import NotFoundError
from app.events.task_events import TaskQueuedEventWriter
from app.models import Order
from app.redis.streams import RedisTaskPublisher
from app.repositories import KitchenTaskRepository, OrderRepository
from app.schemas import KitchenTaskRead, OrderCreate, OrderCreatedRead, OrderRead, RecipeSnapshot
from app.task_builder import TaskBuilder

logger = logging.getLogger(__name__)


class OrderNotFoundError(NotFoundError):
    error = "order_not_found"
    message = "Order not found"


class OrderCreationService:
    def __init__(
        self,
        session: AsyncSession,
        kitchen_client: KitchenServiceClient,
        menu_client: MenuServiceClient,
        task_publisher: RedisTaskPublisher | None,
        task_event_writer: TaskQueuedEventWriter,
        task_builder: TaskBuilder | None = None,
    ) -> None:
        self.session = session
        self.kitchen_client = kitchen_client
        self.menu_client = menu_client
        self.task_publisher = task_publisher
        self.task_event_writer = task_event_writer
        self.orders = OrderRepository(session)
        self.tasks = KitchenTaskRepository(session)
        self.task_builder = task_builder or TaskBuilder()

    async def create_order(self, payload: OrderCreate) -> OrderCreatedRead:
        await self.kitchen_client.get_kitchen(payload.kitchen_id)
        kitchen_menu = await self.menu_client.get_kitchen_menu(payload.kitchen_id)
        menu_item_names = {item.id: item.name for item in kitchen_menu}
        available_ids = {
            item.id
            for item in kitchen_menu
            if item.status == "active" and item.is_available
        }

        recipes: dict[UUID, RecipeSnapshot] = {}
        for item in payload.items:
            if item.menu_item_id not in available_ids:
                raise MenuItemNotAvailableError()
            recipe = await self.menu_client.get_recipe(item.menu_item_id)
            if not recipe.steps:
                raise RecipeStepsNotFoundError()
            recipes[item.menu_item_id] = recipe

        try:
            order = await self.orders.create_order(payload)
            order_items = [
                await self.orders.create_order_item(order.id, item.menu_item_id, item.quantity)
                for item in payload.items
            ]
            built = self.task_builder.build(order.id, order_items, recipes)
            await self.tasks.add_tasks(built.tasks, built.dependencies)
            await self.session.commit()
            await self.session.refresh(order, attribute_names=["items"])
            queued_tasks_count = await self._publish_and_queue_tasks(order, built.tasks, menu_item_names)
            return OrderCreatedRead(
                id=order.id,
                kitchen_id=order.kitchen_id,
                status=order.status,
                pickup_deadline=order.pickup_deadline,
                items=order.items,
                tasks_count=len(built.tasks),
                queued_tasks_count=queued_tasks_count,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def _publish_and_queue_tasks(
        self,
        order: Order,
        tasks,
        menu_item_names: dict[UUID, str],
    ) -> int:
        if self.task_publisher is None:
            return 0

        published: list[tuple] = []
        for task in tasks:
            stream, redis_message_id = await self.task_publisher.publish_task(
                task,
                order,
                menu_item_names.get(task.menu_item_id),
            )
            published.append((task, stream, redis_message_id))

        try:
            await self.tasks.mark_tasks_queued(published)
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise

        for task, stream, redis_message_id in published:
            try:
                await self.task_event_writer.write_task_queued(task, order, stream, redis_message_id)
            except Exception:
                logger.exception("mongo_event_write_failed", extra={"task_id": str(task.id)})

        return len(published)

    async def get_order(self, order_id: UUID) -> Order:
        order = await self.orders.get_order(order_id)
        if order is None:
            raise OrderNotFoundError()
        return order

    async def get_order_read(self, order_id: UUID) -> OrderRead:
        return OrderRead.model_validate(await self.get_order(order_id))

    async def list_order_tasks(self, order_id: UUID) -> list[KitchenTaskRead]:
        await self.get_order(order_id)
        tasks = await self.tasks.list_by_order(order_id)
        return [
            KitchenTaskRead(
                id=task.id,
                order_id=task.order_id,
                menu_item_id=task.menu_item_id,
                station_type=task.station_type,
                operation=task.operation,
                status=task.status,
                estimated_duration_seconds=task.estimated_duration_seconds,
                station_id=task.station_id,
                kds_task_id=task.kds_task_id,
                attempts=task.attempts,
                queued_at=task.queued_at,
                redis_stream=task.redis_stream,
                redis_message_id=task.redis_message_id,
                recipe_step_order=task.recipe_step_order,
                item_unit_index=task.item_unit_index,
                depends_on_task_ids=[dependency.depends_on_task_id for dependency in task.dependencies],
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task in tasks
        ]
