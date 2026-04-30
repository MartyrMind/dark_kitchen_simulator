from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class SimulatorMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or REGISTRY
        self.claim_attempts = Counter(
            "simulator_claim_attempts_total",
            "Total KDS claim attempts by simulator workers.",
            ["station_id", "worker_id"],
            registry=self.registry,
        )
        self.claim_success = Counter(
            "simulator_claim_success_total",
            "Total successful KDS claims by simulator workers.",
            ["station_id", "worker_id"],
            registry=self.registry,
        )
        self.claim_conflicts = Counter(
            "simulator_claim_conflicts_total",
            "Total KDS claim conflicts by simulator workers.",
            ["station_id", "worker_id", "reason"],
            registry=self.registry,
        )
        self.completed_tasks = Counter(
            "simulator_completed_tasks_total",
            "Total KDS tasks completed by simulator workers.",
            ["station_id", "worker_id"],
            registry=self.registry,
        )
        self.task_duration = Histogram(
            "simulator_task_duration_seconds",
            "Simulated task cooking duration in seconds.",
            ["station_id", "worker_id"],
            registry=self.registry,
        )
        self.poll_errors = Counter(
            "simulator_poll_errors_total",
            "Total simulator worker poll errors.",
            ["station_id", "worker_id", "reason"],
            registry=self.registry,
        )
        self.active_workers = Gauge(
            "simulator_active_workers",
            "Number of active simulator workers.",
            registry=self.registry,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)


_default_metrics: SimulatorMetrics | None = None


def get_default_metrics() -> SimulatorMetrics:
    global _default_metrics
    if _default_metrics is None:
        _default_metrics = SimulatorMetrics()
    return _default_metrics
