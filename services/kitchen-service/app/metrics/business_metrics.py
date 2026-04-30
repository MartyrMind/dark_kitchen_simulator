from prometheus_client import Counter, Gauge


kds_visible_backlog_size = Gauge(
    "kds_visible_backlog_size",
    "Visible KDS backlog size.",
    ["kitchen_id", "station_id", "station_type"],
)
kds_claim_attempts_total = Counter(
    "kds_claim_attempts_total",
    "KDS claim attempts.",
    ["kitchen_id", "station_id", "station_type"],
)
kds_claim_success_total = Counter(
    "kds_claim_success_total",
    "Successful KDS claims.",
    ["kitchen_id", "station_id", "station_type"],
)
kds_claim_conflicts_total = Counter(
    "kds_claim_conflicts_total",
    "KDS claim conflicts.",
    ["kitchen_id", "station_id", "station_type", "reason"],
)
station_busy_slots = Gauge(
    "station_busy_slots",
    "Busy station slots.",
    ["kitchen_id", "station_id", "station_type"],
)
station_capacity = Gauge(
    "station_capacity",
    "Station capacity.",
    ["kitchen_id", "station_id", "station_type"],
)
station_utilization_ratio = Gauge(
    "station_utilization_ratio",
    "Station busy slots divided by capacity.",
    ["kitchen_id", "station_id", "station_type"],
)


def update_station_gauges(station, visible_backlog_size: int | None = None) -> None:
    labels = (str(station.kitchen_id), str(station.id), str(station.station_type))
    station_busy_slots.labels(*labels).set(station.busy_slots)
    station_capacity.labels(*labels).set(station.capacity)
    ratio = station.busy_slots / station.capacity if station.capacity else 0
    station_utilization_ratio.labels(*labels).set(ratio)
    if visible_backlog_size is not None:
        kds_visible_backlog_size.labels(*labels).set(visible_backlog_size)
