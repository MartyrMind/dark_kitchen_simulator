from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    station_id: str


def parse_workers_config(raw_config: str) -> list[WorkerConfig]:
    if not raw_config or not raw_config.strip():
        msg = "SIMULATOR_WORKERS_CONFIG must not be empty"
        raise ValueError(msg)

    workers: list[WorkerConfig] = []
    seen_station_ids: set[str] = set()

    for item in raw_config.split(","):
        item = item.strip()
        if not item or ":" not in item:
            msg = "each worker config item must use station_id:count format"
            raise ValueError(msg)

        station_id, raw_count = (part.strip() for part in item.split(":", 1))
        if not station_id:
            msg = "station_id must not be empty"
            raise ValueError(msg)
        if station_id in seen_station_ids:
            msg = f"duplicate station_id in simulator workers config: {station_id}"
            raise ValueError(msg)
        seen_station_ids.add(station_id)

        try:
            count = int(raw_count)
        except ValueError as exc:
            msg = "worker count must be an integer"
            raise ValueError(msg) from exc
        if count <= 0:
            msg = "worker count must be greater than 0"
            raise ValueError(msg)

        for index in range(1, count + 1):
            workers.append(WorkerConfig(worker_id=f"{station_id}-worker-{index}", station_id=station_id))

    return workers
