from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class KdsTask(BaseModel):
    kds_task_id: int | str
    task_id: str
    order_id: str
    station_id: int | str
    operation: str
    menu_item_name: str | None = None
    status: str
    estimated_duration_seconds: int
    pickup_deadline: datetime | None = None
    displayed_at: datetime


class ClaimResponse(BaseModel):
    kds_task_id: int | str
    task_id: str
    station_id: int | str
    status: str
    claimed_by: str
    claimed_at: datetime


class CompleteResponse(BaseModel):
    kds_task_id: int | str
    task_id: str
    station_id: int | str
    status: str
    claimed_by: str
    completed_at: datetime


class ClaimConflict(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RetryableKdsError(Exception):
    pass


class KdsClientError(Exception):
    pass


KdsTaskStatus = Literal["displayed", "claimed", "completed"]
