from enum import StrEnum


class OrderStatus(StrEnum):
    created = "created"
    accepted = "accepted"
    scheduled = "scheduled"
    cooking = "cooking"
    assembling = "assembling"
    ready_for_pickup = "ready_for_pickup"
    handed_off = "handed_off"
    delayed = "delayed"
    cancelled = "cancelled"
    failed = "failed"


class TaskStatus(StrEnum):
    created = "created"
    queued = "queued"
    displayed = "displayed"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"
    retrying = "retrying"
    cancelled = "cancelled"
