# Fulfillment Service

Fulfillment Service owns orders, order items, global kitchen task state, and task dependencies.

Stage 4 boundary: this service creates kitchen tasks with `status=created` only. It does not publish to Redis, does not mark tasks as `queued`, and does not implement KDS, workers, Mongo audit events, retries, DLQ, or dispatch logic.

## Local Setup

```bash
cd services/fulfillment-service
poetry install
```

Environment variables:

```env
SERVICE_NAME=fulfillment-service
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=readable
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment_service
KITCHEN_SERVICE_URL=http://localhost:8001
MENU_SERVICE_URL=http://localhost:8002
HTTP_TIMEOUT_SECONDS=3
ENABLE_REDIS_PUBLISHING=false
```

For Docker, use service DNS names such as `http://kitchen-service:8000` and `http://menu-service:8000`, plus `LOG_FORMAT=json`.

## Database

```bash
poetry run alembic upgrade head
```

Alembic creates:

- `orders`
- `order_items`
- `kitchen_tasks`
- `task_dependencies`

## Run

```bash
poetry run uvicorn app.main:app --reload
```

or:

```bash
poetry run python -m app.main --port 8000 --reload
```

## Tests

```bash
poetry run pytest
```

## Task Generation

For every order item unit, Fulfillment loads recipe steps from Menu Service, sorts them by `step_order`, creates one task per step, and creates dependencies only between consecutive steps inside the same item unit.

Example: Burger x2 with grill step 1 and packaging step 2 creates four tasks and two dependencies. Packaging for unit 1 depends only on grill for unit 1. Packaging for unit 2 depends only on grill for unit 2.

## API Examples

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
    "pickup_deadline": "2026-04-30T18:45:00Z",
    "items": [
      {
        "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
        "quantity": 2
      }
    ]
  }'
```

```bash
curl http://localhost:8000/orders/{order_id}
```

```bash
curl http://localhost:8000/orders/{order_id}/tasks
```
