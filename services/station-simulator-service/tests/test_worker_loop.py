from datetime import datetime, timezone

from prometheus_client import CollectorRegistry

from app.kds_client.schemas import ClaimConflict, RetryableKdsError
from app.metrics.metrics import SimulatorMetrics
from app.simulator.worker import VirtualWorker


class FakeKdsClient:
    def __init__(self, tasks=None):
        self.tasks = tasks or []
        self.claim_calls = []
        self.complete_calls = []
        self.claim_error = None
        self.poll_error = None
        self.complete_errors = []

    async def get_station_tasks(self, station_id, correlation_id=None):
        if self.poll_error:
            raise self.poll_error
        return self.tasks

    async def claim_task(self, station_id, task_id, worker_id, correlation_id=None):
        self.claim_calls.append((station_id, task_id, worker_id))
        if self.claim_error:
            raise self.claim_error

    async def complete_task(self, station_id, task_id, worker_id, correlation_id=None):
        self.complete_calls.append((station_id, task_id, worker_id))
        if self.complete_errors:
            raise self.complete_errors.pop(0)


class SleepRecorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)


def build_worker(fake_client, sleep):
    return VirtualWorker(
        worker_id="grill_1-worker-1",
        station_id="grill_1",
        kds_client=fake_client,
        metrics=SimulatorMetrics(CollectorRegistry()),
        poll_interval_seconds=1,
        speed_factor=60,
        min_duration_factor=1,
        max_duration_factor=1,
        sleep=sleep,
        random_provider=lambda _min, _max: 1,
    )


async def test_worker_claims_sleeps_and_completes_displayed_task(make_task):
    fake_client = FakeKdsClient([make_task()])
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert fake_client.claim_calls == [("grill_1", "task-1", "grill_1-worker-1")]
    assert sleep.calls == [8]
    assert fake_client.complete_calls == [("grill_1", "task-1", "grill_1-worker-1")]
    assert worker.state.completed_tasks_count == 1


async def test_worker_ignores_non_displayed_tasks(make_task):
    fake_client = FakeKdsClient([make_task(status="claimed")])
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert fake_client.claim_calls == []
    assert sleep.calls == [1]


async def test_worker_picks_earliest_displayed_task(make_task):
    later = make_task(task_id="later", displayed_at="2026-04-30T10:02:00Z")
    earlier = make_task(task_id="earlier", displayed_at="2026-04-30T10:01:00Z")
    fake_client = FakeKdsClient([later, earlier])
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert fake_client.claim_calls[0][1] == "earlier"


async def test_worker_does_not_sleep_cooking_duration_on_claim_conflict(make_task):
    fake_client = FakeKdsClient([make_task()])
    fake_client.claim_error = ClaimConflict("station_capacity_exceeded")
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert fake_client.complete_calls == []
    assert sleep.calls == []


async def test_worker_continues_after_poll_error():
    fake_client = FakeKdsClient()
    fake_client.poll_error = RetryableKdsError("kds_timeout")
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert sleep.calls == [1]
    assert worker.state.last_error == "kds_timeout"


async def test_worker_retries_complete_on_temporary_failure(make_task):
    fake_client = FakeKdsClient([make_task()])
    fake_client.complete_errors = [RetryableKdsError("kds_timeout"), RetryableKdsError("kds_timeout")]
    sleep = SleepRecorder()
    worker = build_worker(fake_client, sleep)

    await worker.run_once()

    assert len(fake_client.complete_calls) == 3
    assert sleep.calls == [8, 1, 1]
    assert worker.state.completed_tasks_count == 1
