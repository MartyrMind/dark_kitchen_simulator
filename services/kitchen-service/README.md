# Kitchen Service

Kitchen Service owns kitchens, stations, station capacity, busy slot counters, and local KDS state for station screens.

Stage 6 implements KDS delivery only: dispatch candidates, idempotent task delivery to a station, and listing displayed station tasks. It intentionally does not implement claim, complete, fail, busy slot consumption, Redis consumers, Kitchen Scheduler Worker logic, or Fulfillment callbacks.

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

## KDS Storage And Events

- `kds_station_tasks` stores tasks visible on station KDS screens with local status `displayed`.
- `task_id` and `order_id` are external Fulfillment references and have no database foreign keys.
- Delivery is idempotent by `idempotency_key`.
- New delivery writes a `KdsTaskDisplayed` audit event to MongoDB collection `kds_events`.
- MongoDB event failures are logged and do not fail KDS delivery.

## Environment

- `SERVICE_NAME`, default `kitchen-service`
- `ENVIRONMENT`, default `local`
- `VERSION`, default `0.1.0`
- `LOG_LEVEL`, default `INFO`
- `LOG_FORMAT`, default `json`
- `DATABASE_URL`, required, loaded from the environment or `.env`
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
