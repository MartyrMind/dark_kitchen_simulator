from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from dk_common.correlation import set_correlation_id, set_request_id
from loguru import logger

from app.kds_client.schemas import ClaimConflict, KdsClientError, KdsTask, RetryableKdsError
from app.metrics.metrics import SimulatorMetrics
from app.simulator.duration import RandomProvider, calculate_simulated_duration


SleepFunc = Callable[[float], Awaitable[None]]


class KdsClientProtocol(Protocol):
    async def get_station_tasks(self, station_id: int | str, correlation_id: str | None = None) -> list[KdsTask]:
        ...

    async def claim_task(
        self,
        station_id: int | str,
        task_id: str,
        worker_id: str,
        correlation_id: str | None = None,
    ):
        ...

    async def complete_task(
        self,
        station_id: int | str,
        task_id: str,
        worker_id: str,
        correlation_id: str | None = None,
    ):
        ...


@dataclass
class WorkerState:
    worker_id: str
    station_id: str
    status: str = "starting"
    current_task_id: str | None = None
    last_error: str | None = None
    last_poll_at: datetime | None = None
    completed_tasks_count: int = 0

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "worker_id": self.worker_id,
            "station_id": self.station_id,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "completed_tasks_count": self.completed_tasks_count,
            "last_error": self.last_error,
        }


class VirtualWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        station_id: str,
        kds_client: KdsClientProtocol,
        metrics: SimulatorMetrics,
        poll_interval_seconds: float,
        speed_factor: float,
        min_duration_factor: float,
        max_duration_factor: float,
        sleep: SleepFunc = asyncio.sleep,
        random_provider: RandomProvider | None = None,
        complete_retry_attempts: int = 3,
    ) -> None:
        self.worker_id = worker_id
        self.station_id = station_id
        self.kds_client = kds_client
        self.metrics = metrics
        self.poll_interval_seconds = poll_interval_seconds
        self.speed_factor = speed_factor
        self.min_duration_factor = min_duration_factor
        self.max_duration_factor = max_duration_factor
        self.sleep = sleep
        self.random_provider = random_provider
        self.complete_retry_attempts = complete_retry_attempts
        self.state = WorkerState(worker_id=worker_id, station_id=station_id)
        self._log = logger.bind(worker_id=worker_id, station_id=station_id)

    async def run(self) -> None:
        self.metrics.active_workers.inc()
        self.state.status = "idle"
        self._log.bind(event="worker_started").info("worker_started")
        try:
            while True:
                await self.run_once()
        except asyncio.CancelledError:
            self.state.status = "stopped"
            self._log.bind(event="worker_stopped").info("worker_stopped")
            raise
        finally:
            self.metrics.active_workers.dec()

    async def run_once(self) -> None:
        correlation_id = str(uuid4())
        request_id = str(uuid4())
        set_correlation_id(correlation_id)
        set_request_id(request_id)
        try:
            await self._run_once(correlation_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.state.status = "error"
            self.state.last_error = str(exc)
            self.metrics.poll_errors.labels(self.station_id, self.worker_id, "unexpected_error").inc()
            self._log.bind(event="worker_error", error=str(exc)).exception("worker_error")
            await self.sleep(self.poll_interval_seconds)
        finally:
            set_correlation_id(None)
            set_request_id(None)

    async def _run_once(self, correlation_id: str) -> None:
        self.state.status = "polling"
        self.state.last_poll_at = datetime.now(UTC)
        self._log.bind(event="poll_started").debug("poll_started")
        try:
            tasks = await self.kds_client.get_station_tasks(self.station_id, correlation_id)
        except (RetryableKdsError, KdsClientError) as exc:
            self.state.status = "idle"
            self.state.last_error = str(exc)
            self.metrics.poll_errors.labels(self.station_id, self.worker_id, str(exc)).inc()
            self._log.bind(event="poll_failed", error=str(exc)).error("poll_failed")
            await self.sleep(self.poll_interval_seconds)
            return

        task = self._select_displayed_task(tasks)
        if task is None:
            self.state.status = "idle"
            await self.sleep(self.poll_interval_seconds)
            return

        bound_log = self._log.bind(
            task_id=task.task_id,
            kds_task_id=task.kds_task_id,
            order_id=task.order_id,
            operation=task.operation,
        )
        bound_log.bind(event="displayed_task_found").info("displayed_task_found")
        self.metrics.claim_attempts.labels(self.station_id, self.worker_id).inc()
        bound_log.bind(event="claim_attempt").info("claim_attempt")

        try:
            await self.kds_client.claim_task(self.station_id, task.task_id, self.worker_id, correlation_id)
        except ClaimConflict as exc:
            self.state.status = "idle"
            self.metrics.claim_conflicts.labels(self.station_id, self.worker_id, exc.reason).inc()
            bound_log.bind(event="claim_conflict", error=exc.reason).info("claim_conflict")
            return
        except (RetryableKdsError, KdsClientError) as exc:
            self.state.status = "idle"
            self.state.last_error = str(exc)
            self.metrics.poll_errors.labels(self.station_id, self.worker_id, str(exc)).inc()
            bound_log.bind(event="claim_failed", error=str(exc)).error("claim_failed")
            await self.sleep(self.poll_interval_seconds)
            return

        self.state.status = "cooking"
        self.state.current_task_id = task.task_id
        self.metrics.claim_success.labels(self.station_id, self.worker_id).inc()
        bound_log.bind(event="claim_success").info("claim_success")

        duration = calculate_simulated_duration(
            task.estimated_duration_seconds,
            self.speed_factor,
            self.min_duration_factor,
            self.max_duration_factor,
            self.random_provider,
        )
        self.metrics.task_duration.labels(self.station_id, self.worker_id).observe(duration)
        bound_log.bind(event="simulated_cooking_started", duration_seconds=duration).info("simulated_cooking_started")
        await self.sleep(duration)
        bound_log.bind(event="simulated_cooking_completed", duration_seconds=duration).info("simulated_cooking_completed")

        if await self._complete_with_retry(task, correlation_id, bound_log):
            self.state.completed_tasks_count += 1
            self.metrics.completed_tasks.labels(self.station_id, self.worker_id).inc()

        self.state.status = "idle"
        self.state.current_task_id = None

    async def _complete_with_retry(self, task: KdsTask, correlation_id: str, bound_log) -> bool:
        last_error: Exception | None = None
        for attempt in range(1, self.complete_retry_attempts + 1):
            bound_log.bind(event="complete_attempt", attempt=attempt).info("complete_attempt")
            try:
                await self.kds_client.complete_task(self.station_id, task.task_id, self.worker_id, correlation_id)
            except (RetryableKdsError, KdsClientError) as exc:
                last_error = exc
                bound_log.bind(event="complete_failed", attempt=attempt, error=str(exc)).error("complete_failed")
                if attempt < self.complete_retry_attempts:
                    await self.sleep(self.poll_interval_seconds)
                continue

            bound_log.bind(event="complete_success").info("complete_success")
            return True

        self.state.last_error = str(last_error) if last_error else "complete_failed"
        return False

    def _select_displayed_task(self, tasks: list[KdsTask]) -> KdsTask | None:
        displayed = [task for task in tasks if task.status == "displayed"]
        if not displayed:
            return None
        return sorted(displayed, key=lambda task: task.displayed_at)[0]
