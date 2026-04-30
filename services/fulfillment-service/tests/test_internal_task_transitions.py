from uuid import uuid4

from tests.conftest import BURGER_ID, KITCHEN_ID


async def _create_order(client, quantity=1):
    response = await client.post(
        "/orders",
        json={
            "kitchen_id": str(KITCHEN_ID),
            "pickup_deadline": "2026-04-30T18:45:00Z",
            "items": [{"menu_item_id": str(BURGER_ID), "quantity": quantity}],
        },
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    tasks_response = await client.get(f"/orders/{order_id}/tasks")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    return response.json(), tasks


def _task(tasks, station_type):
    return next(task for task in tasks if task["station_type"] == station_type)


def _display_payload(station_id=None, kds_task_id=None):
    return {
        "station_id": str(station_id or uuid4()),
        "kds_task_id": str(kds_task_id or uuid4()),
        "displayed_at": "2026-04-30T10:00:01Z",
        "dispatcher_id": "scheduler-worker-1",
    }


def _start_payload(station_id, kds_task_id):
    return {
        "station_id": station_id,
        "kds_task_id": kds_task_id,
        "station_worker_id": "grill-worker-1",
        "started_at": "2026-04-30T10:02:00Z",
    }


def _complete_payload(station_id, kds_task_id, completed_at="2026-04-30T10:08:00Z"):
    return {
        "station_id": station_id,
        "kds_task_id": kds_task_id,
        "station_worker_id": "grill-worker-1",
        "completed_at": completed_at,
    }


async def _display_start_complete(client, task_id):
    displayed = await client.post(f"/internal/tasks/{task_id}/mark-displayed", json=_display_payload())
    assert displayed.status_code == 200
    station_id = displayed.json()["station_id"]
    kds_task_id = displayed.json()["kds_task_id"]
    started = await client.post(f"/internal/tasks/{task_id}/start", json=_start_payload(station_id, kds_task_id))
    assert started.status_code == 200
    completed = await client.post(
        f"/internal/tasks/{task_id}/complete",
        json=_complete_payload(station_id, kds_task_id),
    )
    assert completed.status_code == 200
    return completed


async def test_task_snapshot_and_unknown_task(client):
    order, tasks = await _create_order(client)
    grill = _task(tasks, "grill")

    response = await client.get(f"/internal/tasks/{grill['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == grill["id"]
    assert body["order_id"] == order["id"]
    assert body["kitchen_id"] == str(KITCHEN_ID)
    assert body["pickup_deadline"] == "2026-04-30T18:45:00Z"
    assert body["status"] == "queued"

    missing = await client.get(f"/internal/tasks/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"] == "task_not_found"


async def test_dispatch_readiness_uses_dependencies(client):
    _, tasks = await _create_order(client)
    grill = _task(tasks, "grill")
    packaging = _task(tasks, "packaging")

    first_step = await client.get(f"/internal/tasks/{grill['id']}/dispatch-readiness")
    assert first_step.status_code == 200
    assert first_step.json()["ready_to_dispatch"] is True

    blocked = await client.get(f"/internal/tasks/{packaging['id']}/dispatch-readiness")
    assert blocked.status_code == 200
    assert blocked.json()["ready_to_dispatch"] is False
    assert blocked.json()["waiting_for"] == [grill["id"]]

    await _display_start_complete(client, grill["id"])
    ready = await client.get(f"/internal/tasks/{packaging['id']}/dispatch-readiness")
    assert ready.status_code == 200
    assert ready.json()["ready_to_dispatch"] is True
    assert ready.json()["waiting_for"] == []

    displayed = await client.post(f"/internal/tasks/{packaging['id']}/mark-displayed", json=_display_payload())
    assert displayed.status_code == 200
    not_dispatchable = await client.get(f"/internal/tasks/{packaging['id']}/dispatch-readiness")
    assert not_dispatchable.json()["ready_to_dispatch"] is False
    assert not_dispatchable.json()["reason"] == "task_status_not_dispatchable"


async def test_mark_displayed_idempotency_and_events(client):
    _, tasks = await _create_order(client)
    grill = _task(tasks, "grill")
    payload = _display_payload()

    first = await client.post(f"/internal/tasks/{grill['id']}/mark-displayed", json=payload)
    second = await client.post(f"/internal/tasks/{grill['id']}/mark-displayed", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "displayed"
    assert client.transition_event_writer.events[-1]["event_type"] == "TaskDisplayed"

    conflict_payload = {**payload, "kds_task_id": str(uuid4())}
    conflict = await client.post(f"/internal/tasks/{grill['id']}/mark-displayed", json=conflict_payload)
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "task_already_displayed"


async def test_start_task_transition_validation_and_idempotency(client):
    _, tasks = await _create_order(client)
    grill = _task(tasks, "grill")

    queued_start = await client.post(
        f"/internal/tasks/{grill['id']}/start",
        json=_start_payload(str(uuid4()), str(uuid4())),
    )
    assert queued_start.status_code == 409

    displayed = await client.post(f"/internal/tasks/{grill['id']}/mark-displayed", json=_display_payload())
    station_id = displayed.json()["station_id"]
    kds_task_id = displayed.json()["kds_task_id"]

    mismatch = await client.post(
        f"/internal/tasks/{grill['id']}/start",
        json=_start_payload(str(uuid4()), kds_task_id),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"] == "station_mismatch"

    first = await client.post(f"/internal/tasks/{grill['id']}/start", json=_start_payload(station_id, kds_task_id))
    second = await client.post(f"/internal/tasks/{grill['id']}/start", json=_start_payload(station_id, kds_task_id))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "in_progress"
    assert first.json()["sla_deadline_at"] == "2026-04-30T10:10:00Z"
    assert client.transition_event_writer.events[-1]["event_type"] == "TaskStarted"


async def test_complete_task_and_order_ready_for_pickup(client):
    order, tasks = await _create_order(client)
    grill = _task(tasks, "grill")
    packaging = _task(tasks, "packaging")

    grill_complete = await _display_start_complete(client, grill["id"])
    assert grill_complete.json()["actual_duration_seconds"] == 360
    assert grill_complete.json()["delay_seconds"] == 0

    order_after_first = await client.get(f"/orders/{order['id']}")
    assert order_after_first.json()["status"] != "ready_for_pickup"

    displayed = await client.post(f"/internal/tasks/{packaging['id']}/mark-displayed", json=_display_payload())
    station_id = displayed.json()["station_id"]
    kds_task_id = displayed.json()["kds_task_id"]
    await client.post(f"/internal/tasks/{packaging['id']}/start", json=_start_payload(station_id, kds_task_id))

    invalid = await client.post(
        f"/internal/tasks/{packaging['id']}/complete",
        json=_complete_payload(station_id, kds_task_id, completed_at="2026-04-30T10:01:00Z"),
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"] == "invalid_completion_time"

    complete = await client.post(
        f"/internal/tasks/{packaging['id']}/complete",
        json=_complete_payload(station_id, kds_task_id, completed_at="2026-04-30T10:03:30Z"),
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "done"

    replay = await client.post(
        f"/internal/tasks/{packaging['id']}/complete",
        json=_complete_payload(station_id, kds_task_id, completed_at="2026-04-30T10:03:30Z"),
    )
    assert replay.status_code == 200
    assert replay.json() == complete.json()

    order_ready = await client.get(f"/orders/{order['id']}")
    assert order_ready.json()["status"] == "ready_for_pickup"
    event_types = [event["event_type"] for event in client.transition_event_writer.events]
    assert "TaskCompleted" in event_types
    assert "OrderReadyForPickup" in event_types


async def test_dispatch_failed_and_event_failure_does_not_fail_transition(client):
    _, tasks = await _create_order(client)
    grill = _task(tasks, "grill")
    client.transition_event_writer.fail = True

    failed = await client.post(
        f"/internal/tasks/{grill['id']}/dispatch-failed",
        json={
            "reason": "no_dispatch_candidates",
            "failed_at": "2026-04-30T10:05:00Z",
            "dispatcher_id": "scheduler-worker-1",
            "attempts": 5,
        },
    )
    replay = await client.post(
        f"/internal/tasks/{grill['id']}/dispatch-failed",
        json={
            "reason": "no_dispatch_candidates",
            "failed_at": "2026-04-30T10:05:00Z",
            "dispatcher_id": "scheduler-worker-1",
            "attempts": 5,
        },
    )

    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["attempts"] == 5
    assert replay.status_code == 200

    done_task = _task(tasks, "packaging")
    await _display_start_complete(client, done_task["id"])
    done_to_failed = await client.post(
        f"/internal/tasks/{done_task['id']}/dispatch-failed",
        json={
            "reason": "late_failure",
            "failed_at": "2026-04-30T10:05:00Z",
            "dispatcher_id": "scheduler-worker-1",
        },
    )
    assert done_to_failed.status_code == 409
