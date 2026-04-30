# Kitchen Service

Kitchen Service owns kitchens, stations, station capacity, busy slot counters, and local KDS state for station screens.

Stage 9 implements manual KDS worker actions: displayed tasks can be claimed, claimed tasks can be completed, and Kitchen Service calls Fulfillment Service over HTTP for the global task transitions. It intentionally does not implement Station Simulator Service, simulated cooking sleeps, Redis consumers, or Kitchen Scheduler Worker logic.

## Endpoints

- `GET /health`
- `POST /kitchens`
- `GET /kitchens`
- `GET /kitchens/{kitchen_id}`
- `POST /kitchens/{kitchen_id}/stations`
- `GET /kitchens/{kitchen_id}/stations`
- `GET /kitchens/{kitchen_id}/stations?station_type=grill`
- `PATCH /stations/{station_id}/capacity`
- `PATCH /stations/{station_id}/status`
- `GET /internal/kds/dispatch-candidates?kitchen_id=1&station_type=grill`
- `POST /internal/kds/stations/{station_id}/tasks`
- `GET /kds/stations/{station_id}/tasks`
- `POST /kds/stations/{station_id}/tasks/{task_id}/claim`
- `POST /kds/stations/{station_id}/tasks/{task_id}/complete`

## KDS Storage And Events

- `kds_station_tasks` stores tasks visible on station KDS screens with local statuses `displayed`, `claimed`, and `completed`.
- `task_id` and `order_id` are external Fulfillment references and have no database foreign keys.
- Delivery is idempotent by `idempotency_key`.
- New delivery writes a `KdsTaskDisplayed` audit event to MongoDB collection `kds_events`.
- Claim writes `KdsTaskClaimed` and `StationBusySlotOccupied`.
- Complete writes `KdsTaskCompleted` and `StationBusySlotReleased`.
- Rejected or compensated claims write `KdsTaskClaimRejected`.
- MongoDB event failures are logged and do not fail KDS delivery.

## KDS Claim And Complete

Local status transitions:

```text
displayed -> claimed -> completed
```

Claim rules:

- only `displayed` tasks can be claimed;
- the station must be `available`;
- `station.busy_slots < station.capacity` is required;
- claim sets `claimed_by`, `claimed_at`, and increments `busy_slots`;
- double claim is protected with row locks in the claim transaction;
- after the local claim commits, Kitchen calls `POST /internal/tasks/{task_id}/start` on Fulfillment.

If Fulfillment `/start` fails, Kitchen compensates the local claim: the task returns to `displayed`, `claimed_by` and `claimed_at` are cleared, and `busy_slots` is decremented without going below zero.

Complete rules:

- only `claimed` tasks can be completed;
- only the worker stored in `claimed_by` can complete the task;
- Kitchen calls `POST /internal/tasks/{task_id}/complete` on Fulfillment before finalizing local completion;
- after Fulfillment succeeds, the task becomes `completed`, `completed_at` is set, and `busy_slots` is decremented once.

If Fulfillment `/complete` fails, the local task remains `claimed` and the busy slot stays occupied so the worker can retry.

## Environment

- `SERVICE_NAME`, default `kitchen-service`
- `ENVIRONMENT`, default `local`
- `VERSION`, default `0.1.0`
- `LOG_LEVEL`, default `INFO`
- `LOG_FORMAT`, default `json`
- `DATABASE_URL`, required, loaded from the environment or `.env`
- `FULFILLMENT_SERVICE_URL`, default `http://localhost:8003`
- `HTTP_TIMEOUT_SECONDS`, default `3`
- `MONGO_URL`, default `mongodb://localhost:27017`
- `MONGO_DATABASE`, default `dark_kitchen_events`
- `MONGO_EVENTS_ENABLED`, default `true`

## Local Development

```bash
cd services/kitchen-service
cp .env.example .env
poetry config virtualenvs.in-project true --local
poetry install
poetry run alembic upgrade head
poetry run python -m app.main --port 8001
poetry run pytest
```

Edit `.env` before running migrations or the service so `DATABASE_URL` points to your local PostgreSQL database.

The service connects to `dk-common` as a Poetry path dependency from `../../libs/python/dk_common`.

## Manual KDS Check

```bash
curl "http://localhost:8001/internal/kds/dispatch-candidates?kitchen_id=1&station_type=grill"
```

```bash
curl -X POST http://localhost:8001/internal/kds/stations/1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-1" \
  -d '{
    "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
    "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
    "kitchen_id": 1,
    "station_type": "grill",
    "operation": "cook_patty",
    "menu_item_name": "Burger",
    "estimated_duration_seconds": 480,
    "pickup_deadline": "2026-04-30T18:45:00Z",
    "idempotency_key": "8f39f9fc-9c17-4995-8767-fd7e62c44852:dispatch:v1"
  }'
```

Repeating the same delivery returns `200 OK` with the same `kds_task_id`.

```bash
curl http://localhost:8001/kds/stations/1/tasks
```

Claim:

```bash
curl -X POST http://localhost:8001/kds/stations/1/tasks/8f39f9fc-9c17-4995-8767-fd7e62c44852/claim \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-claim-1" \
  -d '{
    "station_worker_id": "grill-worker-1"
  }'
```

Duplicate claim returns `409 Conflict` with `error = task_already_claimed`.

Complete:

```bash
curl -X POST http://localhost:8001/kds/stations/1/tasks/8f39f9fc-9c17-4995-8767-fd7e62c44852/complete \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-complete-1" \
  -d '{
    "station_worker_id": "grill-worker-1"
  }'
```

Completing by a different worker returns `409 Conflict` with `error = task_claimed_by_another_worker`.
