from prometheus_client import Counter, Histogram


orders_created_total = Counter("orders_created_total", "Orders created.", ["kitchen_id"])
orders_cancelled_total = Counter("orders_cancelled_total", "Orders cancelled.", ["kitchen_id"])
orders_ready_total = Counter("orders_ready_total", "Orders ready for pickup.", ["kitchen_id"])
orders_handed_off_total = Counter("orders_handed_off_total", "Orders handed off.", ["kitchen_id"])
orders_delayed_total = Counter("orders_delayed_total", "Orders delayed.", ["kitchen_id"])

tasks_queued_total = Counter("tasks_queued_total", "Kitchen tasks queued.", ["kitchen_id", "station_type"])
tasks_displayed_total = Counter("tasks_displayed_total", "Kitchen tasks displayed.", ["kitchen_id", "station_type"])
tasks_started_total = Counter("tasks_started_total", "Kitchen tasks started.", ["kitchen_id", "station_type"])
tasks_completed_total = Counter("tasks_completed_total", "Kitchen tasks completed.", ["kitchen_id", "station_type"])
tasks_failed_total = Counter("tasks_failed_total", "Kitchen tasks failed.", ["kitchen_id", "station_type"])

task_actual_duration_seconds = Histogram(
    "task_actual_duration_seconds",
    "Actual task duration in seconds.",
    ["kitchen_id", "station_type"],
)
task_delay_seconds = Histogram(
    "task_delay_seconds",
    "Task delay beyond SLA in seconds.",
    ["kitchen_id", "station_type"],
)


def kitchen_label(kitchen_id) -> str:
    return str(kitchen_id)


def station_type_label(station_type) -> str:
    return str(station_type)
