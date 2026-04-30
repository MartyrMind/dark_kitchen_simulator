# Agent Task Spec: Stage 5 - Redis Streams and queued tasks

Encoding note:
This file is ASCII-only on purpose.
It contains no Cyrillic text and no typographic Unicode characters.
Use this version if the agent console shows broken Russian text.

---

## 0. Context

The project is a polyglot monorepo for a dark kitchen order fulfillment system.

Previous stages should already exist:

```text
Stage 1:
  libs/python/dk-common
  common settings, logging, correlation middleware, health helper, errors

Stage 2:
  services/kitchen-service
  kitchens and stations management without KDS

Stage 3:
  services/menu-service
  menu items, recipe steps, kitchen menu availability

Stage 4:
  services/fulfillment-service
  orders, order_items, kitchen_tasks, task_dependencies
  POST /orders creates kitchen_tasks with status = created
  no Redis publishing yet
```

This stage extends:

```text
services/fulfillment-service
```

The goal is to publish newly created kitchen tasks to Redis Streams and move them to status:

```text
queued
```

---

## 1. Goal

Add asynchronous task publication to Redis Streams.

At the end of this stage:

```text
1. POST /orders still validates Kitchen Service and Menu Service.
2. POST /orders still creates order, order_items, kitchen_tasks, task_dependencies.
3. Each created kitchen_task is published to Redis Stream.
4. Each published kitchen_task is moved from created to queued.
5. Redis stream name is based on kitchen_id and station_type.
6. A minimal TaskQueued event is written to MongoDB.
7. There is a test or reproducible manual check for Redis Streams.
```

Stage boundary:

```text
This stage publishes tasks.
This stage does not consume tasks.
This stage does not dispatch tasks to KDS.
This stage does not implement worker logic.
```

---

## 2. Scope

Implement in Fulfillment Service:

```text
1. Redis configuration.
2. Redis async client.
3. Redis task message schema.
4. Redis stream publisher.
5. Update POST /orders flow:
   - create tasks
   - publish tasks
   - set task.status = queued
6. Minimal MongoDB TaskQueued event writer.
7. Optional database fields for publish traceability.
8. Tests for:
   - stream name
   - message payload
   - created -> queued transition
   - no dispatch logic
9. README updates.
10. Optional docker-compose service configuration for Redis and MongoDB.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- Kitchen Scheduler Worker
- Redis consumer group
- XREADGROUP
- XACK
- XPENDING
- retry/backoff
- DLQ
- station selection
- KDS delivery
- Kitchen Service KDS endpoints
- mark-displayed endpoint
- start endpoint
- complete endpoint
- dispatch-readiness endpoint
- Prometheus metrics
- Grafana dashboards
- full MongoDB event log system
- order ready_for_pickup transition
```

Important:

```text
Redis publishing belongs to this stage.
Redis consuming belongs to a later stage.
```

---

## 4. Existing Fulfillment Service behavior before this stage

Before Stage 5, POST /orders should:

```text
1. Validate kitchen through Kitchen Service.
2. Validate availability through Menu Service.
3. Get recipe steps through Menu Service.
4. Create order.
5. Create order_items.
6. Create kitchen_tasks with status = created.
7. Create task_dependencies.
8. Return created order with tasks_count.
```

After Stage 5, the same endpoint must additionally:

```text
9. Publish each kitchen_task to Redis Streams.
10. Mark each successfully published task as queued.
11. Write TaskQueued event to MongoDB.
```

---

## 5. Dependencies

Update services/fulfillment-service/pyproject.toml.

Runtime dependencies to add:

```toml
redis = "^5.0.0"
motor = "^3.4.0"
```

Keep existing dependencies from Stage 4:

```toml
dk-common = { path = "../../libs/python/dk-common", develop = true }

fastapi = "^0.115.0"
uvicorn = { extras = ["standard"], version = "^0.30.0" }

sqlalchemy = { extras = ["asyncio"], version = "^2.0.0" }
asyncpg = "^0.29.0"
alembic = "^1.13.0"
psycopg = { version = "^3.1.0", extras = ["binary"] }

pydantic = "^2.0.0"
pydantic-settings = "^2.0.0"

httpx = "^0.27.0"
```

Dev dependencies can include:

```toml
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
respx = "^0.21.0"
fakeredis = "^2.23.0"
```

Notes:

```text
redis-py 5.x provides redis.asyncio.
motor is used for async MongoDB writes.
fakeredis can be used for unit tests if real Redis is not available.
```

Do not add a Go worker dependency.
Do not add Prometheus dependencies in this stage unless already present.

---

## 6. dk-common integration rule

Fulfillment Service must continue using dk-common as a normal path dependency:

```toml
dk-common = { path = "../../libs/python/dk-common", develop = true }
```

Correct imports:

```python
from dk_common.logging import configure_logging
from dk_common.correlation import CorrelationIdMiddleware
from dk_common.health import build_health_response
from dk_common.settings import BaseServiceSettings
```

Forbidden:

```python
import sys
sys.path.append("../../libs/python/dk-common")
```

Forbidden:

```text
relative imports from libs using ../../../
```

If dk-common already has a generic Mongo event helper, it may be used.
If not, implement a local Fulfillment Service Mongo event writer.

Do not put Fulfillment domain events into dk-common.

Correct ownership:

```text
dk-common may know how to write generic infrastructure events.
fulfillment-service owns the TaskQueued event shape and semantics.
```

---

## 7. Settings

Update services/fulfillment-service/app/core/config.py.

Add settings:

```python
from functools import lru_cache

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "fulfillment-service"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment_service"
    )

    kitchen_service_url: str = "http://localhost:8001"
    menu_service_url: str = "http://localhost:8002"
    http_timeout_seconds: float = 3.0

    redis_url: str = "redis://localhost:6379/0"
    redis_task_stream_prefix: str = "stream:kitchen"
    redis_publish_enabled: bool = True

    mongo_url: str = "mongodb://localhost:27017"
    mongo_database: str = "dark_kitchen_events"
    mongo_events_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
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

REDIS_URL=redis://localhost:6379/0
REDIS_TASK_STREAM_PREFIX=stream:kitchen
REDIS_PUBLISH_ENABLED=true

MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true
```

Docker env example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/fulfillment_service
KITCHEN_SERVICE_URL=http://kitchen-service:8000
MENU_SERVICE_URL=http://menu-service:8000
REDIS_URL=redis://redis:6379/0
MONGO_URL=mongodb://mongo:27017
LOG_FORMAT=json
```

---

## 8. Redis Streams

### 8.1. Stream naming

Fulfillment Service must publish tasks to streams by kitchen_id and station_type.

Format:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

Example:

```text
stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:grill
stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:packaging
```

Implement a pure helper function:

```python
def build_task_stream_name(kitchen_id: UUID | str, station_type: str) -> str:
    ...
```

Expected output:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

### 8.2. Redis message payload

Publish one Redis Stream message per kitchen_task.

Required message fields:

```text
task_id
order_id
kitchen_id
station_type
operation
menu_item_id
menu_item_name
estimated_duration_seconds
pickup_deadline
attempt
```

Recommended extra fields:

```text
correlation_id
created_at
recipe_step_order
item_unit_index
```

Payload example:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "operation": "cook_patty",
  "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
  "menu_item_name": "Burger",
  "estimated_duration_seconds": "480",
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "attempt": "1",
  "recipe_step_order": "1",
  "item_unit_index": "1"
}
```

Important Redis note:

```text
Redis Stream field values should be strings, bytes, int, or float.
For consistent tests, serialize UUIDs and datetimes to strings.
```

### 8.3. Redis client

Create:

```text
app/redis/
  __init__.py
  client.py
  streams.py
```

Example client factory:

```python
from redis.asyncio import Redis

from app.core.config import get_settings


def create_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)
```

Example publisher class:

```python
class RedisTaskPublisher:
    def __init__(self, redis: Redis, stream_prefix: str = "stream:kitchen"):
        self.redis = redis
        self.stream_prefix = stream_prefix

    async def publish_task(self, message: RedisTaskMessage) -> str:
        stream_name = build_task_stream_name(
            message.kitchen_id,
            message.station_type,
        )
        redis_id = await self.redis.xadd(stream_name, message.to_redis_fields())
        return redis_id
```

Do not implement XREADGROUP in this stage.

---

## 9. Database changes

Stage 4 already created:

```text
orders
order_items
kitchen_tasks
task_dependencies
```

For Stage 5, add optional fields to kitchen_tasks if they do not exist yet:

```text
queued_at             timestamp with timezone, nullable
redis_stream          string, nullable
redis_message_id      string, nullable
```

These fields are recommended for debugging and idempotency.

If you choose not to add these fields, tests must still verify queued status and Redis message existence.

Recommended migration:

```text
add queued_at to kitchen_tasks
add redis_stream to kitchen_tasks
add redis_message_id to kitchen_tasks
create index on kitchen_tasks.status
create index on kitchen_tasks.redis_stream
```

Status rule:

```text
created -> queued
```

In this stage, queued means:

```text
The task has been saved in Fulfillment DB and a Redis Stream message has been published.
```

---

## 10. MongoDB TaskQueued event

### 10.1. Requirement

Write a minimal TaskQueued event to MongoDB when a task is successfully published to Redis.

Collection:

```text
task_events
```

Event shape:

```json
{
  "event_type": "TaskQueued",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "payload": {
    "stream": "stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:grill",
    "redis_message_id": "1714470000000-0",
    "operation": "cook_patty",
    "estimated_duration_seconds": 480
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:00:00Z"
}
```

### 10.2. Mongo client

Create:

```text
app/events/
  __init__.py
  mongo.py
  task_events.py
```

Use motor:

```python
from motor.motor_asyncio import AsyncIOMotorClient
```

Behavior:

```text
If MONGO_EVENTS_ENABLED=false:
  do not write events.

If MongoDB is temporarily unavailable:
  log the error.
  Do not fail order creation only because TaskQueued event write failed.
```

Reason:

```text
Redis publish and queued status are part of the core flow.
Mongo event is diagnostic/audit.
```

### 10.3. Scope warning

Do not implement all domain events yet.

Only TaskQueued is required in this stage.

---

## 11. Order creation flow after Stage 5

Recommended flow:

```text
1. Validate request.
2. Validate kitchen through Kitchen Service.
3. Validate menu availability through Menu Service.
4. Load recipes through Menu Service.
5. Start DB transaction.
6. Create order.
7. Create order_items.
8. Create kitchen_tasks with status = created.
9. Create task_dependencies.
10. Commit DB transaction.
11. Publish each created task to Redis Stream.
12. For each successfully published task:
    - update task.status = queued
    - set attempts = 1
    - set queued_at
    - optionally set redis_stream
    - optionally set redis_message_id
13. Write TaskQueued event to MongoDB.
14. Return order response.
```

Why publish after DB commit:

```text
Redis is not part of the PostgreSQL transaction.
Publishing after commit avoids Redis messages that point to rolled-back tasks.
```

Failure behavior:

```text
If external validation fails:
  do not create local DB rows.

If local DB transaction fails:
  do not publish to Redis.

If Redis publish fails after DB commit:
  order exists
  tasks remain status = created
  return 503 or a clear error to the caller
  log the failure
```

Important:

```text
Do not silently mark tasks as queued if Redis publish failed.
```

Optional simpler MVP behavior:

```text
Fail the whole POST /orders response with 503 if Redis publishing fails.
Keep created tasks in DB with status = created.
```

Later stages can add outbox/retry.

---

## 12. Idempotency and consistency notes

This stage does not require a full outbox pattern.

However, implement these safeguards where simple:

```text
1. Do not publish the same task twice from the same code path.
2. Only publish tasks with status = created.
3. Only move task to queued after xadd succeeds.
4. Store redis_message_id if the field exists.
5. Store redis_stream if the field exists.
```

Do not implement:

```text
- pending publish scanner
- outbox table
- deduplication in Redis
- retry scheduler
```

Those can be added later if needed.

---

## 13. Public API impact

### 13.1. POST /orders

POST /orders keeps the same request shape as Stage 4.

Request:

```json
{
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "items": [
    {
      "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
      "quantity": 2
    }
  ]
}
```

Response should now indicate that tasks are queued.

Example response:

```json
{
  "id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "status": "created",
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "items": [
    {
      "id": "2f451da5-c8d7-4053-814f-d6994da6f912",
      "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
      "quantity": 2
    }
  ],
  "tasks_count": 4,
  "queued_tasks_count": 4,
  "created_at": "2026-04-30T10:00:00Z",
  "updated_at": "2026-04-30T10:00:00Z"
}
```

Order status can remain:

```text
created
```

Do not implement order cooking lifecycle yet.

### 13.2. GET /orders/{order_id}/tasks

Tasks returned by this endpoint should now show:

```text
status = queued
attempts = 1
queued_at not null if field exists
redis_stream not null if field exists
redis_message_id not null if field exists
```

Example task:

```json
{
  "id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
  "station_type": "grill",
  "operation": "cook_patty",
  "status": "queued",
  "estimated_duration_seconds": 480,
  "station_id": null,
  "kds_task_id": null,
  "attempts": 1,
  "queued_at": "2026-04-30T10:00:01Z",
  "redis_stream": "stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:grill",
  "redis_message_id": "1714470000000-0",
  "recipe_step_order": 1,
  "item_unit_index": 1,
  "depends_on_task_ids": [],
  "created_at": "2026-04-30T10:00:00Z",
  "updated_at": "2026-04-30T10:00:01Z"
}
```

---

## 14. Internal helper functions

Implement pure helpers and test them.

### 14.1. Stream name helper

```python
def build_task_stream_name(kitchen_id: UUID | str, station_type: str) -> str:
    return f"stream:kitchen:{kitchen_id}:station:{station_type}"
```

### 14.2. Message builder

Create a message builder that converts a KitchenTask into Redis fields.

Suggested API:

```python
def build_redis_task_message(
    task: KitchenTask,
    order: Order,
    menu_item_name: str | None,
    correlation_id: str | None,
) -> dict[str, str]:
    ...
```

Required output keys:

```text
task_id
order_id
kitchen_id
station_type
operation
menu_item_id
menu_item_name
estimated_duration_seconds
pickup_deadline
attempt
```

Rules:

```text
All UUIDs must be strings.
All datetimes must be ISO strings.
All numbers can be strings for consistency.
menu_item_name can be empty string if not available.
attempt should be "1" for first publish.
```

---

## 15. API errors

Add or reuse stable machine-readable errors.

Format:

```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

Additional error codes for this stage:

```text
redis_unavailable
task_publish_failed
mongo_event_write_failed
```

Recommended behavior:

```text
redis_unavailable -> 503
task_publish_failed -> 503
mongo_event_write_failed -> log only, do not fail request
```

Do not put Fulfillment domain errors into dk-common.

---

## 16. Tests

### 16.1. Test command

Tests must run from services/fulfillment-service:

```bash
poetry run pytest
```

### 16.2. Test types

Use a mix of:

```text
pure unit tests for stream name and message builder
service-level tests with fake Redis publisher
component tests with mocked external HTTP services
optional Redis integration test with real Redis
```

### 16.3. Required tests

#### test_redis_streams.py

Check:

```text
build_task_stream_name returns stream:kitchen:{kitchen_id}:station:{station_type}
build_redis_task_message includes required fields
build_redis_task_message serializes UUIDs as strings
build_redis_task_message serializes datetimes as ISO strings
```

#### test_order_creation_with_redis.py

With fake external clients and fake Redis publisher, check:

```text
POST /orders creates tasks
tasks are published to Redis
tasks move from created to queued
attempts becomes 1
queued_tasks_count equals tasks_count
```

#### test_order_creation_redis_failure.py

Check:

```text
If Redis publishing fails:
  POST /orders returns 503
  tasks are not marked queued
  tasks remain created
```

If the implementation rolls back all local rows on Redis failure, document it and update the test accordingly.
Preferred MVP behavior:

```text
DB rows remain for diagnostics.
Tasks remain status = created.
```

#### test_task_queued_event.py

With fake Mongo event writer, check:

```text
TaskQueued event is written after successful Redis publish
event contains event_type = TaskQueued
event contains task_id, order_id, kitchen_id, station_type
event contains stream and redis_message_id in payload
```

Also check:

```text
If Mongo write fails:
  order creation still succeeds
  task remains queued
  error is logged
```

#### test_no_worker_logic.py

Check by code or behavior:

```text
No XREADGROUP usage
No XACK usage
No consumer group creation
No KDS call
No station_id assigned
No kds_task_id assigned
```

This can be a lightweight unit test or a manual review checklist in README.

### 16.4. Manual Redis check

Add a manual check to README.

Example:

```bash
redis-cli XINFO STREAM stream:kitchen:{kitchen_id}:station:grill
redis-cli XRANGE stream:kitchen:{kitchen_id}:station:grill - +
```

Expected result:

```text
Redis stream contains one message per queued kitchen_task for that station_type.
```

---

## 17. README updates

Update services/fulfillment-service/README.md.

Add:

```text
1. Redis requirement.
2. MongoDB requirement for TaskQueued events.
3. New env variables:
   - REDIS_URL
   - REDIS_TASK_STREAM_PREFIX
   - REDIS_PUBLISH_ENABLED
   - MONGO_URL
   - MONGO_DATABASE
   - MONGO_EVENTS_ENABLED
4. How to run Redis locally.
5. How to run MongoDB locally.
6. How to verify Redis Streams manually.
7. Stage boundary: this service publishes only, it does not consume.
```

Example local dependencies:

```bash
docker run --rm -p 6379:6379 redis:7
docker run --rm -p 27017:27017 mongo:7
```

Example Redis inspection:

```bash
redis-cli KEYS 'stream:kitchen:*'
redis-cli XRANGE stream:kitchen:{kitchen_id}:station:grill - +
```

---

## 18. Docker Compose notes

If there is a compose file, add or verify:

```yaml
services:
  redis:
    image: redis:7
    ports:
      - "6379:6379"

  mongo:
    image: mongo:7
    ports:
      - "27017:27017"

  fulfillment-service:
    environment:
      REDIS_URL: redis://redis:6379/0
      MONGO_URL: mongodb://mongo:27017
      MONGO_DATABASE: dark_kitchen_events
```

Do not add Kitchen Scheduler Worker yet.

---

## 19. Definition of Done

Stage is complete when:

```text
1. Fulfillment Service has Redis configuration.
2. Fulfillment Service has Redis async client.
3. Fulfillment Service publishes one Redis Stream message per created kitchen_task.
4. Stream name is stream:kitchen:{kitchen_id}:station:{station_type}.
5. Redis message includes required task fields.
6. POST /orders moves successfully published tasks from created to queued.
7. POST /orders does not mark task queued if Redis publish failed.
8. GET /orders/{order_id}/tasks shows queued tasks after successful order creation.
9. attempts is set to 1 for queued tasks.
10. Optional queued_at, redis_stream, redis_message_id are filled if fields exist.
11. TaskQueued event is written to MongoDB after successful publish.
12. MongoDB failure does not fail order creation.
13. Tests cover stream name, message payload, queued transition, Redis failure, and TaskQueued event.
14. README explains how to inspect Redis Streams manually.
15. No worker, no XREADGROUP, no XACK, no retry, no DLQ, no KDS delivery, no station selection.
```

---

## 20. Short instruction for the agent

Implement Stage 5 in services/fulfillment-service.

Add:

```text
redis.asyncio client
RedisTaskPublisher
stream name builder
Redis message builder
TaskQueued Mongo event writer
queued task transition
tests
README updates
```

POST /orders must now:

```text
1. Create order and kitchen_tasks as before.
2. Publish each kitchen_task to Redis Stream.
3. Set each published task to status = queued.
4. Set attempts = 1.
5. Write TaskQueued event to MongoDB.
```

Use stream format:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

Do not implement:

```text
worker
consumer group
XREADGROUP
XACK
retry
DLQ
KDS delivery
mark-displayed
start
complete
station selection
```
