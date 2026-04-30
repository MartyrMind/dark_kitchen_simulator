from app.domain.statuses import TaskStatus


ALLOWED_TRANSITIONS: set[tuple[TaskStatus, TaskStatus]] = {
    (TaskStatus.queued, TaskStatus.displayed),
    (TaskStatus.retrying, TaskStatus.displayed),
    (TaskStatus.displayed, TaskStatus.in_progress),
    (TaskStatus.in_progress, TaskStatus.done),
    (TaskStatus.queued, TaskStatus.failed),
    (TaskStatus.retrying, TaskStatus.failed),
}


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return (current, target) in ALLOWED_TRANSITIONS
