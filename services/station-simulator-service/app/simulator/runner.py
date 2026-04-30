from __future__ import annotations

import asyncio

from loguru import logger

from app.core.config import Settings
from app.kds_client.client import KdsClient
from app.metrics.metrics import SimulatorMetrics
from app.simulator.config_parser import WorkerConfig, parse_workers_config
from app.simulator.worker import VirtualWorker


class SimulatorRunner:
    def __init__(self, settings: Settings, metrics: SimulatorMetrics) -> None:
        self.settings = settings
        self.metrics = metrics
        self.client: KdsClient | None = None
        self.workers: list[VirtualWorker] = []
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if not self.settings.simulator_enabled:
            logger.bind(event="simulator_disabled").info("simulator_disabled")
            return

        worker_configs = parse_workers_config(self.settings.simulator_workers_config)
        self.client = KdsClient(self.settings.kitchen_service_url, self.settings.http_timeout_seconds)
        self.workers = [self._build_worker(config) for config in worker_configs]
        self.tasks = [asyncio.create_task(worker.run()) for worker in self.workers]
        logger.bind(event="simulator_started", worker_count=len(self.workers)).info("simulator_started")

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        if self.client is not None:
            await self.client.close()
            self.client = None

        logger.bind(event="simulator_stopped").info("simulator_stopped")

    def worker_states(self) -> list[dict[str, str | int | None]]:
        return [worker.state.to_dict() for worker in self.workers]

    def _build_worker(self, config: WorkerConfig) -> VirtualWorker:
        assert self.client is not None
        return VirtualWorker(
            worker_id=config.worker_id,
            station_id=config.station_id,
            kds_client=self.client,
            metrics=self.metrics,
            poll_interval_seconds=self.settings.simulator_poll_interval_ms / 1000,
            speed_factor=self.settings.simulator_speed_factor,
            min_duration_factor=self.settings.simulator_min_duration_factor,
            max_duration_factor=self.settings.simulator_max_duration_factor,
        )
