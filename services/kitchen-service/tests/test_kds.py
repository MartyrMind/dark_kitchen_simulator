from uuid import uuid4

from app import events


async def _create_station(client, *, station_type="grill", visible_backlog_limit=4, status=None):
    kitchen = await client.post("/kitchens", json={"name": f"Kitchen {uuid4()}"})
    assert kitchen.status_code == 201
    kitchen_id = kitchen.json()["id"]
    station = await client.post(
        f"/kitchens/{kitchen_id}/stations",
        json={
            "name": f"Station {uuid4()}",
            "station_type": station_type,
            "capacity": 2,
            "visible_backlog_limit": visible_backlog_limit,
        },
    )
    assert station.status_code == 201
    station_id = station.json()["id"]
    if status is not None:
        patched = await client.patch(f"/stations/{station_id}/status", json={"status": status})
        assert patched.status_code == 200
    return kitchen_id, station_id


def _delivery_payload(kitchen_id, *, task_id=None, station_type="grill", idempotency_key=None):
    task_id = task_id or uuid4()
    return {
        "task_id": str(task_id),
        "order_id": str(uuid4()),
        "kitchen_id": kitchen_id,
        "station_type": station_type,
        "operation": "cook_patty",
        "menu_item_name": "Burger",
        "estimated_duration_seconds": 480,
        "pickup_deadline": "2026-04-30T18:45:00Z",
        "idempotency_key": idempotency_key or f"{task_id}:dispatch:v1",
    }


async def test_dispatch_candidates_filter_by_station_state_type_and_backlog(client):
    kitchen_id, station_id = await _create_station(client, station_type="grill", visible_backlog_limit=1)
    await _create_station(client, station_type="fryer")
    unavailable_kitchen_id, unavailable_station_id = await _create_station(client, status="unavailable")
    maintenance_kitchen_id, maintenance_station_id = await _create_station(client, status="maintenance")

    candidates = await client.get(
        "/internal/kds/dispatch-candidates",
        params={"kitchen_id": kitchen_id, "station_type": "grill"},
    )
    assert candidates.status_code == 200
    assert candidates.json()[0]["station_id"] == station_id
    assert candidates.json()[0]["visible_backlog_size"] == 0

    delivered = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(kitchen_id),
    )
    assert delivered.status_code == 201

    full_candidates = await client.get(
        "/internal/kds/dispatch-candidates",
        params={"kitchen_id": kitchen_id, "station_type": "grill"},
    )
    assert full_candidates.status_code == 200
    assert full_candidates.json() == []

    unavailable_candidates = await client.get(
        "/internal/kds/dispatch-candidates",
        params={"kitchen_id": unavailable_kitchen_id, "station_type": "grill"},
    )
    maintenance_candidates = await client.get(
        "/internal/kds/dispatch-candidates",
        params={"kitchen_id": maintenance_kitchen_id, "station_type": "grill"},
    )
    assert unavailable_candidates.json() == []
    assert maintenance_candidates.json() == []
    assert unavailable_station_id != maintenance_station_id


async def test_kds_delivery_creates_displayed_task_and_does_not_change_busy_slots(client):
    kitchen_id, station_id = await _create_station(client)

    before = await client.get(f"/kitchens/{kitchen_id}/stations")
    assert before.json()[0]["busy_slots"] == 0

    response = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(kitchen_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["station_id"] == station_id
    assert body["status"] == "displayed"

    tasks = await client.get(f"/kds/stations/{station_id}/tasks")
    assert tasks.status_code == 200
    assert len(tasks.json()) == 1
    assert tasks.json()[0]["kds_task_id"] == body["kds_task_id"]
    assert tasks.json()[0]["status"] == "displayed"

    after = await client.get(f"/kitchens/{kitchen_id}/stations")
    assert after.json()[0]["busy_slots"] == 0


async def test_kds_delivery_validation_errors(client):
    kitchen_id, station_id = await _create_station(client, visible_backlog_limit=1)
    other_kitchen_id, _ = await _create_station(client)

    unknown = await client.post("/internal/kds/stations/404/tasks", json=_delivery_payload(kitchen_id))
    assert unknown.status_code == 404
    assert unknown.json()["error"] == "station_not_found"

    unavailable_kitchen_id, unavailable_station_id = await _create_station(client, status="unavailable")
    unavailable = await client.post(
        f"/internal/kds/stations/{unavailable_station_id}/tasks",
        json=_delivery_payload(unavailable_kitchen_id),
    )
    assert unavailable.status_code == 409
    assert unavailable.json()["error"] == "station_not_available"

    kitchen_mismatch = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(other_kitchen_id),
    )
    assert kitchen_mismatch.status_code == 409
    assert kitchen_mismatch.json()["error"] == "station_kitchen_mismatch"

    type_mismatch = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(kitchen_id, station_type="fryer"),
    )
    assert type_mismatch.status_code == 409
    assert type_mismatch.json()["error"] == "station_type_mismatch"

    first = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=_delivery_payload(kitchen_id))
    assert first.status_code == 201
    full = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=_delivery_payload(kitchen_id))
    assert full.status_code == 409
    assert full.json()["error"] == "visible_backlog_limit_exceeded"

    invalid_duration = _delivery_payload(kitchen_id)
    invalid_duration["estimated_duration_seconds"] = 0
    assert (await client.post(f"/internal/kds/stations/{station_id}/tasks", json=invalid_duration)).status_code == 422

    missing_key = _delivery_payload(kitchen_id)
    missing_key.pop("idempotency_key")
    assert (await client.post(f"/internal/kds/stations/{station_id}/tasks", json=missing_key)).status_code == 422


async def test_kds_delivery_idempotency(client):
    kitchen_id, station_id = await _create_station(client)
    task_id = uuid4()
    payload = _delivery_payload(kitchen_id, task_id=task_id, idempotency_key=f"{task_id}:dispatch:v1")

    first = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=payload)
    second = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["kds_task_id"] == first.json()["kds_task_id"]

    tasks = await client.get(f"/kds/stations/{station_id}/tasks")
    assert len(tasks.json()) == 1

    duplicate_task = _delivery_payload(kitchen_id, task_id=task_id, idempotency_key=f"{task_id}:dispatch:v2")
    duplicate = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=duplicate_task)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "kds_task_already_exists"


async def test_kds_event_is_written_for_new_delivery(monkeypatch, client):
    class FakeEventWriter:
        def __init__(self):
            self.events = []

        async def write_task_displayed(self, task, correlation_id):
            self.events.append((task, correlation_id))

    fake = FakeEventWriter()
    monkeypatch.setattr(events, "event_writer", fake)

    kitchen_id, station_id = await _create_station(client)
    response = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(kitchen_id),
        headers={"X-Correlation-ID": "corr-test-1"},
    )

    assert response.status_code == 201
    assert len(fake.events) == 1
    task, correlation_id = fake.events[0]
    assert task.task_id == response.json()["task_id"]
    assert task.id == response.json()["kds_task_id"]
    assert task.idempotency_key.endswith(":dispatch:v1")
    assert correlation_id == "corr-test-1"

    replay = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json={
            "task_id": response.json()["task_id"],
            "order_id": str(uuid4()),
            "kitchen_id": kitchen_id,
            "station_type": "grill",
            "operation": "cook_patty",
            "estimated_duration_seconds": 480,
            "idempotency_key": task.idempotency_key,
        },
    )
    assert replay.status_code == 200
    assert len(fake.events) == 1


async def test_kds_event_failure_does_not_fail_delivery(monkeypatch, client):
    class FailingEventWriter:
        async def write_task_displayed(self, task, correlation_id):
            raise RuntimeError("mongo down")

    monkeypatch.setattr(events, "event_writer", FailingEventWriter())

    kitchen_id, station_id = await _create_station(client)
    response = await client.post(
        f"/internal/kds/stations/{station_id}/tasks",
        json=_delivery_payload(kitchen_id),
    )

    assert response.status_code == 201


async def test_claim_and_complete_are_not_implemented(client):
    kitchen_id, station_id = await _create_station(client)
    delivered = await client.post(f"/internal/kds/stations/{station_id}/tasks", json=_delivery_payload(kitchen_id))
    task_id = delivered.json()["task_id"]

    claim = await client.post(f"/kds/stations/{station_id}/tasks/{task_id}/claim")
    complete = await client.post(f"/kds/stations/{station_id}/tasks/{task_id}/complete")

    assert claim.status_code == 404
    assert complete.status_code == 404
