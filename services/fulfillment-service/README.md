# Fulfillment Service

Fulfillment Service owns orders, order items, global kitchen task state, and task dependencies.

Stage 5 boundary: this service publishes newly created kitchen tasks to Redis Streams and then marks them as `queued`. It does not consume Redis streams and does not implement KDS, workers, retries, DLQ, or dispatch logic.

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
REDIS_URL=redis://localhost:6379/0
REDIS_TASK_STREAM_PREFIX=stream:kitchen
REDIS_PUBLISH_ENABLED=true
MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true
```

For Docker, use service DNS names such as `http://kitchen-service:8000`, `http://menu-service:8000`, `redis://redis:6379/0`, and `mongodb://mongo:27017`, plus `LOG_FORMAT=json`.

## Local Infrastructure

```bash
docker run --rm -p 6379:6379 redis:7
docker run --rm -p 27017:27017 mongo:7
```

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

After the local DB transaction commits, each task is published to:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

Only successfully published tasks are moved from `created` to `queued`, with `attempts=1`, `queued_at`, `redis_stream`, and `redis_message_id` filled. A minimal `TaskQueued` document is written to MongoDB collection `task_events`; Mongo write failures are logged but do not fail order creation.

## Redis Inspection

```bash
redis-cli KEYS 'stream:kitchen:*'
redis-cli XRANGE stream:kitchen:{kitchen_id}:station:grill - +
redis-cli XINFO STREAM stream:kitchen:{kitchen_id}:station:grill
```

Expected result: one Redis Stream message per queued kitchen task for that station type.

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
