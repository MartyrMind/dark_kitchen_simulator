from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import KitchenStatus, StationStatus, StationType


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
