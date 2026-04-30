from datetime import UTC, datetime, timedelta
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
from app.domain.errors import ConflictError, NotFoundError
from app.domain.statuses import OrderStatus, TaskStatus
from app.domain.transitions import can_transition
from app.events.task_events import TaskQueuedEventWriter, TaskTransitionEventWriter
from app.metrics import business_metrics
from app.models import KitchenTask, Order
from app.redis.streams import RedisTaskPublisher
from app.repositories import KitchenTaskRepository, OrderRepository
from app.schemas import (
    CompleteTaskRequest,
    CompleteTaskResponse,
    DispatchFailedRequest,
    DispatchReadinessResponse,
    KitchenTaskRead,
    MarkDisplayedRequest,
    MarkDisplayedResponse,
    OrderCreate,
    OrderCreatedRead,
    OrderRead,
    RecipeSnapshot,
    StartTaskRequest,
    StartTaskResponse,
    TaskSnapshotResponse,
)
from app.task_builder import TaskBuilder

logger = logging.getLogger(__name__)


class OrderNotFoundError(NotFoundError):
    error = "order_not_found"
    message = "Order not found"


class TaskNotFoundError(NotFoundError):
    error = "task_not_found"
    message = "Task not found"


class InvalidTaskStatusTransitionError(ConflictError):
    error = "invalid_task_status_transition"
    message = "Invalid task status transition"


class TaskAlreadyDisplayedError(ConflictError):
    error = "task_already_displayed"
    message = "Task is already displayed"


class TaskAlreadyStartedError(ConflictError):
    error = "task_already_started"
    message = "Task is already started"


class TaskAlreadyCompletedError(ConflictError):
    error = "task_already_completed"
    message = "Task is already completed"


class StationMismatchError(ConflictError):
    error = "station_mismatch"
    message = "Station does not match task"


class KdsTaskMismatchError(ConflictError):
    error = "kds_task_mismatch"
    message = "KDS task does not match task"


class InvalidCompletionTimeError(ConflictError):
    error = "invalid_completion_time"
    message = "Completion time cannot be before start time"


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
            business_metrics.orders_created_total.labels(business_metrics.kitchen_label(order.kitchen_id)).inc()
            await self._safe_optional_creation_event_write(
                "write_order_created",
                order,
                len(built.tasks),
            )
            await self._safe_optional_creation_event_write(
                "write_kitchen_tasks_created",
                order,
                len(built.tasks),
            )
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
            business_metrics.tasks_queued_total.labels(
                business_metrics.kitchen_label(order.kitchen_id),
                business_metrics.station_type_label(task.station_type),
            ).inc()
            try:
                await self.task_event_writer.write_task_queued(task, order, stream, redis_message_id)
            except Exception:
                logger.exception("mongo_event_write_failed", extra={"task_id": str(task.id)})
                await self._safe_optional_creation_event_write(
                    "write_audit_event",
                    "MongoEventWriteFailed",
                    task_id=str(task.id),
                    order_id=str(order.id),
                    kitchen_id=str(order.kitchen_id),
                    payload={"collection": "task_events", "event_type": "TaskQueued"},
                )

        return len(published)

    async def _safe_optional_creation_event_write(self, method_name: str, *args, **kwargs) -> None:
        log_extra = {key: value for key, value in kwargs.items() if key in {"task_id", "order_id"}}
        method = getattr(self.task_event_writer, method_name, None)
        if method is None:
            return
        try:
            await method(*args, **kwargs)
        except Exception:
            logger.exception("mongo_event_write_failed", extra=log_extra)

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


class TaskTransitionService:
    def __init__(
        self,
        session: AsyncSession,
        event_writer: TaskTransitionEventWriter,
    ) -> None:
        self.session = session
        self.event_writer = event_writer
        self.orders = OrderRepository(session)
        self.tasks = KitchenTaskRepository(session)

    async def get_snapshot(self, task_id: UUID) -> TaskSnapshotResponse:
        task = await self.tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        return self._snapshot(task)

    async def dispatch_readiness(self, task_id: UUID) -> DispatchReadinessResponse:
        task = await self.tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        if task.status not in {TaskStatus.queued, TaskStatus.retrying}:
            return DispatchReadinessResponse(
                task_id=task.id,
                ready_to_dispatch=False,
                waiting_for=[],
                reason="task_status_not_dispatchable",
            )
        waiting_for = await self.tasks.unfinished_dependencies(task.id)
        return DispatchReadinessResponse(
            task_id=task.id,
            ready_to_dispatch=len(waiting_for) == 0,
            waiting_for=waiting_for,
            reason=None if not waiting_for else "waiting_for_dependencies",
        )

    async def mark_displayed(self, task_id: UUID, payload: MarkDisplayedRequest) -> MarkDisplayedResponse:
        task = await self._get_task_for_transition(task_id)
        if task.status == TaskStatus.displayed:
            self._validate_same_station_and_kds(task, payload.station_id, payload.kds_task_id, TaskAlreadyDisplayedError)
            return self._mark_displayed_response(task)
        self._require_transition(task.status, TaskStatus.displayed)

        task.station_id = payload.station_id
        task.kds_task_id = payload.kds_task_id
        task.displayed_at = payload.displayed_at
        task.status = TaskStatus.displayed
        await self.session.commit()
        business_metrics.tasks_displayed_total.labels(
            business_metrics.kitchen_label(task.order.kitchen_id),
            business_metrics.station_type_label(task.station_type),
        ).inc()
        await self._safe_event_write(self.event_writer.write_task_displayed(task, payload.dispatcher_id))
        return self._mark_displayed_response(task)

    async def start_task(self, task_id: UUID, payload: StartTaskRequest) -> StartTaskResponse:
        task = await self._get_task_for_transition(task_id)
        if task.status == TaskStatus.in_progress:
            self._validate_same_station_and_kds(task, payload.station_id, payload.kds_task_id, TaskAlreadyStartedError)
            return self._start_response(task)
        self._require_transition(task.status, TaskStatus.in_progress)
        self._validate_same_station_and_kds(task, payload.station_id, payload.kds_task_id)

        task.started_at = payload.started_at
        task.sla_deadline_at = payload.started_at + timedelta(seconds=task.estimated_duration_seconds)
        task.status = TaskStatus.in_progress
        task.order.status = OrderStatus.cooking
        await self.session.commit()
        business_metrics.tasks_started_total.labels(
            business_metrics.kitchen_label(task.order.kitchen_id),
            business_metrics.station_type_label(task.station_type),
        ).inc()
        await self._safe_event_write(self.event_writer.write_task_started(task, payload.station_worker_id))
        return self._start_response(task)

    async def complete_task(self, task_id: UUID, payload: CompleteTaskRequest) -> CompleteTaskResponse:
        task = await self._get_task_for_transition(task_id)
        if task.status == TaskStatus.done:
            self._validate_same_station_and_kds(task, payload.station_id, payload.kds_task_id, TaskAlreadyCompletedError)
            return self._complete_response(task)
        self._require_transition(task.status, TaskStatus.done)
        self._validate_same_station_and_kds(task, payload.station_id, payload.kds_task_id)
        started_at = self._as_utc(task.started_at)
        completed_at = self._as_utc(payload.completed_at)
        sla_deadline_at = self._as_utc(task.sla_deadline_at)
        if started_at is None or completed_at < started_at:
            raise InvalidCompletionTimeError()

        task.completed_at = completed_at
        task.actual_duration_seconds = int((completed_at - started_at).total_seconds())
        if sla_deadline_at is None:
            task.delay_seconds = 0
        else:
            task.delay_seconds = max(0, int((completed_at - sla_deadline_at).total_seconds()))
        task.status = TaskStatus.done

        order_ready = await self.tasks.all_order_tasks_done(task.order_id)
        completed_count = 0
        if order_ready:
            task.order.status = OrderStatus.ready_for_pickup
            completed_count = await self.tasks.completed_order_tasks_count(task.order_id)

        await self.session.commit()
        labels = (
            business_metrics.kitchen_label(task.order.kitchen_id),
            business_metrics.station_type_label(task.station_type),
        )
        business_metrics.tasks_completed_total.labels(*labels).inc()
        business_metrics.task_actual_duration_seconds.labels(*labels).observe(task.actual_duration_seconds or 0)
        business_metrics.task_delay_seconds.labels(*labels).observe(task.delay_seconds or 0)
        if order_ready:
            business_metrics.orders_ready_total.labels(business_metrics.kitchen_label(task.order.kitchen_id)).inc()
        await self._safe_event_write(self.event_writer.write_task_completed(task, payload.station_worker_id))
        if order_ready:
            await self._safe_event_write(self.event_writer.write_order_ready_for_pickup(task.order, completed_count))
        return self._complete_response(task)

    async def dispatch_failed(self, task_id: UUID, payload: DispatchFailedRequest) -> TaskSnapshotResponse:
        task = await self._get_task_for_transition(task_id)
        if task.status == TaskStatus.failed:
            return self._snapshot(task)
        self._require_transition(task.status, TaskStatus.failed)
        if payload.attempts is not None and payload.attempts > task.attempts:
            task.attempts = payload.attempts
        task.status = TaskStatus.failed
        await self.session.commit()
        business_metrics.tasks_failed_total.labels(
            business_metrics.kitchen_label(task.order.kitchen_id),
            business_metrics.station_type_label(task.station_type),
        ).inc()
        await self._safe_event_write(
            self.event_writer.write_task_dispatch_failed(task, payload.reason, payload.dispatcher_id)
        )
        return self._snapshot(task)

    async def _get_task_for_transition(self, task_id: UUID) -> KitchenTask:
        task = await self.tasks.get_for_update(task_id)
        if task is None:
            raise TaskNotFoundError()
        return task

    def _require_transition(self, current: TaskStatus, target: TaskStatus) -> None:
        if not can_transition(current, target):
            raise InvalidTaskStatusTransitionError(
                f"Cannot transition task from {current} to {target}",
                details={"current_status": current, "target_status": target},
            )

    def _validate_same_station_and_kds(
        self,
        task: KitchenTask,
        station_id: UUID,
        kds_task_id: UUID,
        already_error_type: type[ConflictError] | None = None,
    ) -> None:
        if task.station_id != station_id:
            if already_error_type is not None:
                raise already_error_type()
            raise StationMismatchError()
        if task.kds_task_id != kds_task_id:
            if already_error_type is not None:
                raise already_error_type()
            raise KdsTaskMismatchError()

    async def _safe_event_write(self, write_coro) -> None:
        try:
            await write_coro
        except Exception:
            logger.exception("mongo_event_write_failed")

    def _snapshot(self, task: KitchenTask) -> TaskSnapshotResponse:
        return TaskSnapshotResponse(
            task_id=task.id,
            order_id=task.order_id,
            kitchen_id=task.order.kitchen_id,
            menu_item_id=task.menu_item_id,
            station_type=task.station_type,
            station_id=task.station_id,
            kds_task_id=task.kds_task_id,
            operation=task.operation,
            status=task.status,
            estimated_duration_seconds=task.estimated_duration_seconds,
            pickup_deadline=self._as_utc(task.order.pickup_deadline),
            attempts=task.attempts,
            displayed_at=self._as_utc(task.displayed_at),
            started_at=self._as_utc(task.started_at),
            sla_deadline_at=self._as_utc(task.sla_deadline_at),
            completed_at=self._as_utc(task.completed_at),
            actual_duration_seconds=task.actual_duration_seconds,
            delay_seconds=task.delay_seconds,
        )

    def _mark_displayed_response(self, task: KitchenTask) -> MarkDisplayedResponse:
        return MarkDisplayedResponse(
            task_id=task.id,
            status=task.status,
            station_id=task.station_id,
            kds_task_id=task.kds_task_id,
            displayed_at=self._as_utc(task.displayed_at),
        )

    def _start_response(self, task: KitchenTask) -> StartTaskResponse:
        return StartTaskResponse(
            task_id=task.id,
            status=task.status,
            station_id=task.station_id,
            kds_task_id=task.kds_task_id,
            started_at=self._as_utc(task.started_at),
            sla_deadline_at=self._as_utc(task.sla_deadline_at),
        )

    def _complete_response(self, task: KitchenTask) -> CompleteTaskResponse:
        return CompleteTaskResponse(
            task_id=task.id,
            status=task.status,
            station_id=task.station_id,
            kds_task_id=task.kds_task_id,
            started_at=self._as_utc(task.started_at),
            completed_at=self._as_utc(task.completed_at),
            actual_duration_seconds=task.actual_duration_seconds,
            delay_seconds=task.delay_seconds,
        )

    def _as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
