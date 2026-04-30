from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import MenuItemStatus, StationType


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    status: MenuItemStatus = MenuItemStatus.active


class MenuItemRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: MenuItemStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecipeStepCreate(BaseModel):
    station_type: StationType
    operation: str = Field(min_length=1, max_length=120)
    duration_seconds: int = Field(gt=0)
    step_order: int = Field(gt=0)


class RecipeStepRead(BaseModel):
    id: UUID
    menu_item_id: UUID
    station_type: StationType
    operation: str
    duration_seconds: int
    step_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecipeStepSummary(BaseModel):
    id: UUID
    station_type: StationType
    operation: str
    duration_seconds: int
    step_order: int

    model_config = ConfigDict(from_attributes=True)


class RecipeRead(BaseModel):
    menu_item_id: UUID
    steps: list[RecipeStepSummary]


class AvailabilityUpsert(BaseModel):
    is_available: bool


class AvailabilityRead(BaseModel):
    kitchen_id: UUID
    menu_item_id: UUID
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KitchenMenuItemRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: MenuItemStatus
    is_available: bool
