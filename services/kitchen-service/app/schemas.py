from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import KdsTaskStatus, KitchenStatus, StationStatus, StationType


class KitchenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class KitchenRead(BaseModel):
    id: int
    name: str
    status: KitchenStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    station_type: StationType
    capacity: int = Field(ge=1)
    visible_backlog_limit: int = Field(ge=1)


class StationRead(BaseModel):
    id: int
    kitchen_id: int
    name: str
    station_type: StationType
    status: StationStatus
    capacity: int
    busy_slots: int
    visible_backlog_limit: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationCapacityUpdate(BaseModel):
    capacity: int = Field(ge=1)


class StationStatusUpdate(BaseModel):
    status: StationStatus


class KdsTaskDeliveryRequest(BaseModel):
    task_id: UUID
    order_id: UUID
    kitchen_id: int
    station_type: StationType
    operation: str = Field(min_length=1, max_length=120)
    menu_item_name: str | None = Field(default=None, max_length=120)
    estimated_duration_seconds: int = Field(gt=0)
    pickup_deadline: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)


class KdsTaskDeliveryResponse(BaseModel):
    kds_task_id: int
    task_id: UUID
    station_id: int
    status: KdsTaskStatus


class DispatchCandidateResponse(BaseModel):
    station_id: int
    station_type: StationType
    status: StationStatus
    capacity: int
    busy_slots: int
    visible_backlog_size: int
    visible_backlog_limit: int
    health: str


class KdsStationTaskResponse(BaseModel):
    kds_task_id: int
    task_id: UUID
    order_id: UUID
    station_id: int
    operation: str
    menu_item_name: str | None
    status: KdsTaskStatus
    estimated_duration_seconds: int
    pickup_deadline: datetime | None
    displayed_at: datetime


class KdsTaskClaimRequest(BaseModel):
    station_worker_id: str = Field(min_length=1, max_length=120)
    claimed_at: datetime | None = None


class KdsTaskClaimResponse(BaseModel):
    kds_task_id: int
    task_id: UUID
    station_id: int
    status: KdsTaskStatus
    claimed_by: str
    claimed_at: datetime


class KdsTaskCompleteRequest(BaseModel):
    station_worker_id: str = Field(min_length=1, max_length=120)
    completed_at: datetime | None = None


class KdsTaskCompleteResponse(BaseModel):
    kds_task_id: int
    task_id: UUID
    station_id: int
    status: KdsTaskStatus
    claimed_by: str
    completed_at: datetime
