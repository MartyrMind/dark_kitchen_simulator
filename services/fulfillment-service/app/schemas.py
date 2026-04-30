from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.statuses import OrderStatus, TaskStatus


class OrderItemCreate(BaseModel):
    menu_item_id: UUID
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    kitchen_id: UUID
    pickup_deadline: datetime | None = None
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    id: UUID
    menu_item_id: UUID
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: UUID
    kitchen_id: UUID
    status: OrderStatus
    pickup_deadline: datetime | None
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCreatedRead(OrderRead):
    tasks_count: int
    queued_tasks_count: int = 0


class KitchenTaskRead(BaseModel):
    id: UUID
    order_id: UUID
    menu_item_id: UUID
    station_type: str
    operation: str
    status: TaskStatus
    estimated_duration_seconds: int
    station_id: UUID | None
    kds_task_id: UUID | None
    attempts: int
    queued_at: datetime | None
    redis_stream: str | None
    redis_message_id: str | None
    recipe_step_order: int
    item_unit_index: int
    depends_on_task_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class KitchenSnapshot(BaseModel):
    id: UUID | int
    status: str


class KitchenMenuItemSnapshot(BaseModel):
    id: UUID
    name: str = ""
    status: str
    is_available: bool


class RecipeStepSnapshot(BaseModel):
    station_type: str
    operation: str
    duration_seconds: int = Field(gt=0)
    step_order: int = Field(gt=0)


class RecipeSnapshot(BaseModel):
    menu_item_id: UUID
    steps: list[RecipeStepSnapshot]
