# Agent Task Spec: Stage 7 - Fulfillment internal API for task transitions

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

Stage 5:
  fulfillment-service publishes kitchen_tasks to Redis Streams
  kitchen_tasks move from created to queued
  TaskQueued event is written to MongoDB

Stage 6:
  kitchen-service has local KDS state
  kds_station_tasks table
  internal KDS delivery endpoint
  idempotent KDS delivery
```

This stage extends:

```text
services/fulfillment-service
```

The goal is to prepare Fulfillment Service for interaction with the future Kitchen Scheduler Worker and with Kitchen Service / KDS.

Fulfillment Service remains the only owner of global task business statuses:

```text
created
queued
displayed
in_progress
done
failed
retrying
cancelled
```

---

## 1. Goal

Implement internal Fulfillment APIs for task status transitions.

At the end of this stage:

```text
1. Worker can fetch a task snapshot.
2. Worker can ask whether a task is ready for dispatch.
3. Worker can mark a queued task as displayed after KDS delivery.
4. Kitchen Service / KDS can mark a displayed task as in_progress after claim.
5. Kitchen Service / KDS can mark an in_progress task as done after complete.
6. Fulfillment validates all status transitions.
7. Fulfillment uses task_dependencies for dispatch-readiness.
8. Fulfillment writes MongoDB events for:
   - TaskDisplayed
   - TaskStarted
   - TaskCompleted
   - TaskDispatchFailed
9. Fulfillment checks whether all tasks of an order are done and then sets order.status = ready_for_pickup.
```

Stage boundary:

```text
This stage implements internal Fulfillment endpoints only.
This stage does not implement the worker.
This stage does not consume Redis.
This stage does not implement KDS claim/complete endpoints in Kitchen Service.
```

---

## 2. Scope

Implement in Fulfillment Service:

```text
1. Internal task routes:
   - GET /internal/tasks/{task_id}
   - GET /internal/tasks/{task_id}/dispatch-readiness
   - POST /internal/tasks/{task_id}/mark-displayed
   - POST /internal/tasks/{task_id}/start
   - POST /internal/tasks/{task_id}/complete
   - POST /internal/tasks/{task_id}/dispatch-failed
   - POST /internal/tasks/{task_id}/retry optional
   - POST /internal/tasks/{task_id}/fail optional
2. Status transition validation.
3. Dispatch-readiness based on task_dependencies.
4. Idempotency for mark-displayed, start, and complete where possible.
5. MongoDB task events:
   - TaskDisplayed
   - TaskStarted
   - TaskCompleted
   - TaskDispatchFailed
6. MongoDB order event:
   - OrderReadyForPickup
7. Order ready_for_pickup transition when all tasks are done.
8. Unit and component tests.
9. README updates.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- Kitchen Scheduler Worker
- Redis consumer group
- XREADGROUP
- XACK
- retry/backoff loop
- DLQ stream writing
- Kitchen Service KDS claim endpoint
- Kitchen Service KDS complete endpoint
- Station Simulator
- Prometheus metrics
- Grafana dashboards
- Kubernetes manifests
```

Do not write to Kitchen Service database.

Do not read from Redis in this stage.

Do not call Kitchen Service KDS delivery from Fulfillment Service in this stage.

---

## 4. Existing Fulfillment Service behavior before this stage

Before Stage 7:

```text
POST /orders creates order.
POST /orders creates order_items.
POST /orders creates kitchen_tasks.
POST /orders creates task_dependencies.
Stage 5 publishes tasks to Redis.
Stage 5 sets task.status = queued.
GET /orders/{order_id} works.
GET /orders/{order_id}/tasks works.
```

After Stage 7:

```text
Fulfillment can validate and execute:
queued -> displayed
displayed -> in_progress
in_progress -> done
queued -> failed or retrying
retrying -> queued
```

---

## 5. Dependencies

Fulfillment Service should already have:

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
redis = "^5.0.0"
motor = "^3.4.0"
```

No new runtime dependency is required for this stage in most implementations.

Dev dependencies can include:

```toml
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
respx = "^0.21.0"
```

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

Do not put Fulfillment domain transitions or task events into dk-common.

Correct ownership:

```text
dk-common may contain infrastructure helpers.
fulfillment-service owns task status transitions and task event semantics.
```

---

## 7. Settings

Fulfillment Service should already have Mongo settings from Stage 5.

Verify settings include:

```python
class Settings(BaseServiceSettings):
    service_name: str = "fulfillment-service"

    database_url: str
    mongo_url: str = "mongodb://localhost:27017"
    mongo_database: str = "dark_kitchen_events"
    mongo_events_enabled: bool = True
```

Environment variables:

```env
SERVICE_NAME=fulfillment-service
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=readable

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment_service

MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true
```

Docker env example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/fulfillment_service
MONGO_URL=mongodb://mongo:27017
MONGO_DATABASE=dark_kitchen_events
LOG_FORMAT=json
```

---

## 8. Data model review

The following tables should already exist.

### 8.1. kitchen_tasks

Required fields:

```text
id                            UUID primary key
order_id                      UUID, required, foreign key to orders.id
menu_item_id                  UUID, required
station_type                  string, required
station_id                    UUID, nullable
kds_task_id                   UUID, nullable
operation                     string, required
status                        string, required
estimated_duration_seconds    integer, required
displayed_at                  timestamp with timezone, nullable
started_at                    timestamp with timezone, nullable
sla_deadline_at               timestamp with timezone, nullable
completed_at                  timestamp with timezone, nullable
actual_duration_seconds       integer, nullable
delay_seconds                 integer, nullable
attempts                      integer, required, default 0
queued_at                     timestamp with timezone, nullable
redis_stream                  string, nullable
redis_message_id              string, nullable
created_at                    timestamp with timezone
updated_at                    timestamp with timezone
```

Recommended existing fields from Stage 4:

```text
order_item_id                 UUID, nullable or required
recipe_step_order             integer, nullable or required
item_unit_index               integer, nullable or required
```

### 8.2. task_dependencies

Required fields:

```text
task_id                  UUID, required, foreign key to kitchen_tasks.id
depends_on_task_id       UUID, required, foreign key to kitchen_tasks.id
created_at               timestamp with timezone
```

### 8.3. Alembic changes for this stage

If the Stage 4/5 schema already has all fields, no new migration is required.

If any of these fields are missing, create an Alembic migration to add them:

```text
station_id
kds_task_id
displayed_at
started_at
sla_deadline_at
completed_at
actual_duration_seconds
delay_seconds
attempts
queued_at
redis_stream
redis_message_id
```

Add indexes if missing:

```text
INDEX(kitchen_tasks.status)
INDEX(kitchen_tasks.order_id)
INDEX(kitchen_tasks.station_id)
INDEX(kitchen_tasks.kds_task_id)
```

Do not add foreign keys to Kitchen Service or KDS tables.

---

## 9. Status transition rules

Implement transition validation in one place, not scattered across routes.

Recommended file:

```text
app/domain/transitions.py
```

Allowed transitions for this stage:

```text
queued -> displayed
displayed -> in_progress
in_progress -> done
queued -> retrying
retrying -> queued
queued -> failed
retrying -> failed
displayed -> cancelled
in_progress -> failed
```

Required transitions to implement now:

```text
queued -> displayed
displayed -> in_progress
in_progress -> done
queued -> failed
```

Optional transitions:

```text
queued -> retrying
retrying -> queued
in_progress -> failed
displayed -> cancelled
```

Invalid transitions must return:

```http
409 Conflict
```

Example error:

```json
{
  "error": "invalid_task_status_transition",
  "message": "Cannot transition task from done to displayed",
  "details": {
    "current_status": "done",
    "target_status": "displayed"
  }
}
```

---

## 10. Internal API endpoints

Create or extend:

```text
app/api/routes/internal_tasks.py
```

Recommended prefix:

```text
/internal/tasks
```

Include router in app/main.py.

---

### 10.1. GET /internal/tasks/{task_id}

Return current task snapshot.

Path:

```http
GET /internal/tasks/{task_id}
```

Response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
  "station_type": "grill",
  "station_id": null,
  "kds_task_id": null,
  "operation": "cook_patty",
  "status": "queued",
  "estimated_duration_seconds": 480,
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "attempts": 1,
  "displayed_at": null,
  "started_at": null,
  "completed_at": null
}
```

Notes:

```text
pickup_deadline comes from orders.pickup_deadline.
kitchen_id comes from orders.kitchen_id.
```

Not found:

```http
404 Not Found
```

```json
{
  "error": "task_not_found",
  "message": "Task not found"
}
```

---

### 10.2. GET /internal/tasks/{task_id}/dispatch-readiness

Check if task can be dispatched to KDS.

Path:

```http
GET /internal/tasks/{task_id}/dispatch-readiness
```

Ready response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "ready_to_dispatch": true,
  "waiting_for": []
}
```

Not ready response:

```json
{
  "task_id": "de0c8a5f-233e-4f2c-9b7f-e35942574d9f",
  "ready_to_dispatch": false,
  "waiting_for": [
    "8f39f9fc-9c17-4995-8767-fd7e62c44852"
  ]
}
```

Rules:

```text
1. Task must exist.
2. Task.status must be queued or retrying.
3. If task has no dependencies, ready_to_dispatch = true.
4. If task has dependencies, all dependency tasks must have status = done.
5. waiting_for contains dependency task IDs that are not done.
```

Status behavior:

```text
If task.status is displayed, in_progress, done, cancelled, or failed:
  ready_to_dispatch = false
  include reason field if useful
```

Optional response field:

```json
{
  "reason": "task_status_not_dispatchable"
}
```

Do not change task status in this endpoint.

---

### 10.3. POST /internal/tasks/{task_id}/mark-displayed

Called by the future worker after successful KDS delivery.

Path:

```http
POST /internal/tasks/{task_id}/mark-displayed
```

Request:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "displayed_at": "2026-04-30T10:00:01Z",
  "dispatcher_id": "scheduler-worker-1"
}
```

Processing:

```text
1. Task must exist.
2. Task.status must be queued or retrying.
3. Task must not be cancelled.
4. Set station_id.
5. Set kds_task_id.
6. Set displayed_at.
7. Set status = displayed.
8. Write TaskDisplayed event.
9. Return updated task snapshot.
```

Successful response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "status": "displayed",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "displayed_at": "2026-04-30T10:00:01Z"
}
```

Idempotency:

```text
If task.status is already displayed and station_id/kds_task_id match:
  return 200 with existing displayed snapshot.

If task.status is displayed but station_id or kds_task_id differ:
  return 409 task_already_displayed.

If task.status is in_progress or done:
  return 409 invalid_task_status_transition unless the request exactly matches existing displayed data and no mutation is needed.

If task.status is cancelled or failed:
  return 409 invalid_task_status_transition.
```

Important:

```text
This endpoint does not call Kitchen Service.
The worker calls Kitchen Service first, then calls this endpoint.
```

---

### 10.4. POST /internal/tasks/{task_id}/start

Called by Kitchen Service / KDS after successful claim.

Path:

```http
POST /internal/tasks/{task_id}/start
```

Request:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "station_worker_id": "grill-worker-1",
  "started_at": "2026-04-30T10:02:00Z"
}
```

Processing:

```text
1. Task must exist.
2. Task.status must be displayed.
3. Request station_id must match task.station_id.
4. Request kds_task_id must match task.kds_task_id.
5. Set started_at.
6. Set sla_deadline_at = started_at + estimated_duration_seconds.
7. Set status = in_progress.
8. Write TaskStarted event.
9. If order.status is not cooking, set order.status = cooking.
10. Return updated task snapshot.
```

Successful response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "status": "in_progress",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "started_at": "2026-04-30T10:02:00Z",
  "sla_deadline_at": "2026-04-30T10:10:00Z"
}
```

Idempotency:

```text
If task.status is already in_progress and station_id/kds_task_id match:
  return 200 with existing in_progress snapshot.

If task.status is in_progress but station_id/kds_task_id differ:
  return 409 task_already_started.

If task.status is done:
  return 409 invalid_task_status_transition.
```

---

### 10.5. POST /internal/tasks/{task_id}/complete

Called by Kitchen Service / KDS after worker completes station task.

Path:

```http
POST /internal/tasks/{task_id}/complete
```

Request:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "station_worker_id": "grill-worker-1",
  "completed_at": "2026-04-30T10:08:00Z"
}
```

Processing:

```text
1. Task must exist.
2. Task.status must be in_progress.
3. Request station_id must match task.station_id.
4. Request kds_task_id must match task.kds_task_id.
5. Set completed_at.
6. Calculate actual_duration_seconds = completed_at - started_at.
7. Calculate delay_seconds = max(0, completed_at - sla_deadline_at).
8. Set status = done.
9. Write TaskCompleted event.
10. Check if all tasks for the order are done.
11. If all tasks are done, set order.status = ready_for_pickup.
12. If order becomes ready_for_pickup, write OrderReadyForPickup event.
13. Return updated task snapshot.
```

Successful response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "status": "done",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "started_at": "2026-04-30T10:02:00Z",
  "completed_at": "2026-04-30T10:08:00Z",
  "actual_duration_seconds": 360,
  "delay_seconds": 0
}
```

Idempotency:

```text
If task.status is already done and station_id/kds_task_id match:
  return 200 with existing done snapshot.

If task.status is done but station_id/kds_task_id differ:
  return 409 task_already_completed.
```

Validation:

```text
If completed_at is before started_at:
  return 422 or 409 with invalid_completion_time.
```

---

### 10.6. POST /internal/tasks/{task_id}/dispatch-failed

Called by the future worker when dispatch permanently fails or max attempts is reached.

Path:

```http
POST /internal/tasks/{task_id}/dispatch-failed
```

Request:

```json
{
  "reason": "no_dispatch_candidates",
  "failed_at": "2026-04-30T10:05:00Z",
  "dispatcher_id": "scheduler-worker-1",
  "attempts": 5
}
```

Processing:

```text
1. Task must exist.
2. Task.status should be queued or retrying.
3. Set status = failed.
4. Set attempts if provided and greater than current attempts.
5. Write TaskDispatchFailed event.
6. Return updated task snapshot.
```

Successful response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "status": "failed",
  "attempts": 5
}
```

Idempotency:

```text
If task.status is already failed:
  return 200 with existing failed snapshot.
```

---

### 10.7. POST /internal/tasks/{task_id}/retry optional

Optional endpoint for future retry support.

Path:

```http
POST /internal/tasks/{task_id}/retry
```

Request:

```json
{
  "reason": "no_dispatch_candidates",
  "retry_at": "2026-04-30T10:05:00Z",
  "dispatcher_id": "scheduler-worker-1",
  "attempts": 2
}
```

Processing:

```text
1. Task must exist.
2. Task.status must be queued or retrying.
3. Set status = retrying.
4. Update attempts if provided.
5. Write TaskDispatchRetried event if implemented.
```

This endpoint is optional in Stage 7 because full retry/backoff belongs to the worker stage.

---

## 11. MongoDB events

### 11.1. Collections

Use:

```text
task_events
order_events
```

### 11.2. Event write behavior

Behavior:

```text
If MONGO_EVENTS_ENABLED=false:
  do not write events.

If MongoDB is temporarily unavailable:
  log the error.
  Do not fail the status transition only because event write failed.
```

Reason:

```text
PostgreSQL task status is the source of truth.
Mongo event log is diagnostic/audit.
```

### 11.3. TaskDisplayed event

Write after successful mark-displayed.

```json
{
  "event_type": "TaskDisplayed",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "payload": {
    "dispatcher_id": "scheduler-worker-1"
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:00:01Z"
}
```

### 11.4. TaskStarted event

Write after successful start.

```json
{
  "event_type": "TaskStarted",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "payload": {
    "station_worker_id": "grill-worker-1",
    "started_at": "2026-04-30T10:02:00Z",
    "sla_deadline_at": "2026-04-30T10:10:00Z"
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:02:00Z"
}
```

### 11.5. TaskCompleted event

Write after successful complete.

```json
{
  "event_type": "TaskCompleted",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "payload": {
    "station_worker_id": "grill-worker-1",
    "completed_at": "2026-04-30T10:08:00Z",
    "actual_duration_seconds": 360,
    "delay_seconds": 0
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:08:00Z"
}
```

### 11.6. OrderReadyForPickup event

Write when the last task of the order becomes done.

```json
{
  "event_type": "OrderReadyForPickup",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "payload": {
    "completed_tasks_count": 2
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:08:00Z"
}
```

### 11.7. TaskDispatchFailed event

Write after successful dispatch-failed.

```json
{
  "event_type": "TaskDispatchFailed",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "payload": {
    "reason": "no_dispatch_candidates",
    "dispatcher_id": "scheduler-worker-1",
    "attempts": 5
  },
  "correlation_id": "corr_123",
  "service": "fulfillment-service",
  "created_at": "2026-04-30T10:05:00Z"
}
```

---

## 12. Recommended code structure

Add or extend:

```text
services/fulfillment-service/
  app/
    api/
      routes/
        internal_tasks.py
    domain/
      transitions.py
      statuses.py
      errors.py
    events/
      mongo.py
      task_events.py
      order_events.py
    repositories/
      kitchen_tasks.py
      orders.py
    schemas/
      internal_tasks.py
    services/
      task_transitions.py
      dispatch_readiness.py
```

Preferred flow:

```text
routes -> task_transitions service -> repositories -> SQLAlchemy
task_transitions service -> event writer
```

Do not put transition logic in route handlers.

---

## 13. Pydantic schemas

Create app/schemas/internal_tasks.py.

### 13.1. TaskSnapshotResponse

Fields:

```text
task_id UUID
order_id UUID
kitchen_id UUID
menu_item_id UUID
station_type str
station_id UUID or None
kds_task_id UUID or None
operation str
status str
estimated_duration_seconds int
pickup_deadline datetime or None
attempts int
displayed_at datetime or None
started_at datetime or None
sla_deadline_at datetime or None
completed_at datetime or None
actual_duration_seconds int or None
delay_seconds int or None
```

### 13.2. DispatchReadinessResponse

Fields:

```text
task_id UUID
ready_to_dispatch bool
waiting_for list[UUID]
reason str or None
```

### 13.3. MarkDisplayedRequest

Fields:

```text
station_id UUID
kds_task_id UUID
displayed_at datetime
dispatcher_id str
```

### 13.4. MarkDisplayedResponse

Fields:

```text
task_id UUID
status str
station_id UUID
kds_task_id UUID
displayed_at datetime
```

### 13.5. StartTaskRequest

Fields:

```text
station_id UUID
kds_task_id UUID
station_worker_id str
started_at datetime
```

### 13.6. StartTaskResponse

Fields:

```text
task_id UUID
status str
station_id UUID
kds_task_id UUID
started_at datetime
sla_deadline_at datetime
```

### 13.7. CompleteTaskRequest

Fields:

```text
station_id UUID
kds_task_id UUID
station_worker_id str
completed_at datetime
```

### 13.8. CompleteTaskResponse

Fields:

```text
task_id UUID
status str
station_id UUID
kds_task_id UUID
started_at datetime
completed_at datetime
actual_duration_seconds int
delay_seconds int
```

### 13.9. DispatchFailedRequest

Fields:

```text
reason str
failed_at datetime
dispatcher_id str
attempts int or None
```

---

## 14. API errors

Use stable machine-readable errors.

Format:

```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

Minimum error codes:

```text
task_not_found
order_not_found
invalid_task_status_transition
task_not_ready_to_dispatch
task_already_displayed
task_already_started
task_already_completed
station_mismatch
kds_task_mismatch
invalid_completion_time
validation_error
internal_error
```

Recommended mappings:

```text
task_not_found -> 404
order_not_found -> 404
invalid_task_status_transition -> 409
task_not_ready_to_dispatch -> 409
task_already_displayed -> 409
task_already_started -> 409
task_already_completed -> 409
station_mismatch -> 409
kds_task_mismatch -> 409
invalid_completion_time -> 409 or 422
validation_error -> 422
internal_error -> 500
```

Do not put Fulfillment domain errors into dk-common.

---

## 15. Transactions and concurrency

Status transitions must be transactional.

Recommended transaction pattern:

```text
BEGIN
SELECT kitchen_task FOR UPDATE
validate current status
validate request fields
update task
update order if needed
COMMIT
write Mongo event after commit or within safe post-commit flow
```

Important:

```text
Use row-level locking for transitions to prevent double updates.
Two concurrent complete calls must not produce inconsistent order status.
```

If event write happens after commit and fails:

```text
Log the failure.
Do not roll back the PostgreSQL status transition.
```

---

## 16. Tests

### 16.1. Test command

Tests must run from services/fulfillment-service:

```bash
poetry run pytest
```

### 16.2. Required tests

#### test_task_snapshot.py

Check:

```text
GET /internal/tasks/{task_id} returns task snapshot
snapshot includes kitchen_id from order
snapshot includes pickup_deadline from order
unknown task returns 404
```

#### test_dispatch_readiness.py

Check:

```text
task with no dependencies is ready
task with dependency done is ready
task with dependency queued is not ready
task with dependency displayed is not ready
waiting_for contains unfinished dependency task id
task with status displayed is not dispatchable
task with status done is not dispatchable
```

Main required dependency test:

```text
Given:
  grill task status = done
  packaging task depends on grill task

When:
  GET /internal/tasks/{packaging_task_id}/dispatch-readiness

Then:
  ready_to_dispatch = true
  waiting_for = []
```

Negative dependency test:

```text
Given:
  grill task status = queued
  packaging task depends on grill task

Then:
  ready_to_dispatch = false
  waiting_for = [grill_task_id]
```

#### test_mark_displayed.py

Check:

```text
queued -> displayed succeeds
retrying -> displayed succeeds
displayed_at is set
station_id is set
kds_task_id is set
TaskDisplayed event is written
same request repeated returns 200 and does not change data
different kds_task_id for already displayed task returns 409
done -> displayed returns 409
```

#### test_start_task.py

Check:

```text
displayed -> in_progress succeeds
started_at is set
sla_deadline_at = started_at + estimated_duration_seconds
order.status becomes cooking
TaskStarted event is written
station_id mismatch returns 409
kds_task_id mismatch returns 409
queued -> in_progress returns 409
same request repeated returns 200
```

#### test_complete_task.py

Check:

```text
in_progress -> done succeeds
completed_at is set
actual_duration_seconds is calculated
delay_seconds is calculated
TaskCompleted event is written
station_id mismatch returns 409
kds_task_id mismatch returns 409
displayed -> done returns 409
same request repeated returns 200
completed_at before started_at returns 409 or 422
```

#### test_order_ready_for_pickup.py

Check:

```text
order with two tasks:
  when first task completes, order.status is not ready_for_pickup
  when second task completes, order.status becomes ready_for_pickup
  OrderReadyForPickup event is written
```

#### test_dispatch_failed.py

Check:

```text
queued -> failed succeeds
retrying -> failed succeeds
attempts is updated if provided
TaskDispatchFailed event is written
done -> failed returns 409
already failed returns 200
```

#### test_event_write_failure.py

With fake Mongo event writer:

```text
If Mongo write fails:
  task transition still succeeds
  error is logged
```

#### test_no_worker_logic.py

Check by code or behavior:

```text
No XREADGROUP usage
No XACK usage
No Redis consumer group creation
No Kitchen Service KDS delivery call
No station selection
```

---

## 17. Manual check scenario

Add to README.

### 17.1. Task snapshot

```bash
curl http://localhost:8000/internal/tasks/{task_id}
```

Expected:

```text
status = queued
```

### 17.2. Dispatch readiness

```bash
curl http://localhost:8000/internal/tasks/{task_id}/dispatch-readiness
```

Expected for first recipe step:

```text
ready_to_dispatch = true
```

### 17.3. Mark displayed

```bash
curl -X POST http://localhost:8000/internal/tasks/{task_id}/mark-displayed \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-1" \
  -d '{
    "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
    "displayed_at": "2026-04-30T10:00:01Z",
    "dispatcher_id": "scheduler-worker-1"
  }'
```

Expected:

```text
status = displayed
```

### 17.4. Start task

```bash
curl -X POST http://localhost:8000/internal/tasks/{task_id}/start \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-1" \
  -d '{
    "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
    "station_worker_id": "grill-worker-1",
    "started_at": "2026-04-30T10:02:00Z"
  }'
```

Expected:

```text
status = in_progress
```

### 17.5. Complete task

```bash
curl -X POST http://localhost:8000/internal/tasks/{task_id}/complete \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-1" \
  -d '{
    "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
    "station_worker_id": "grill-worker-1",
    "completed_at": "2026-04-30T10:08:00Z"
  }'
```

Expected:

```text
status = done
actual_duration_seconds is present
delay_seconds is present
```

---

## 18. README updates

Update services/fulfillment-service/README.md.

Add:

```text
1. Internal task transition API section.
2. Status transition table.
3. Dispatch-readiness explanation.
4. MongoDB event behavior.
5. Manual curl examples.
6. Stage boundary:
   - Fulfillment exposes internal APIs
   - worker is not implemented yet
   - KDS claim/complete endpoints are not implemented here
```

Example commands:

```bash
cd services/fulfillment-service

poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
poetry run pytest
```

---

## 19. Definition of Done

Stage is complete when:

```text
1. GET /internal/tasks/{task_id} works.
2. GET /internal/tasks/{task_id}/dispatch-readiness works.
3. dispatch-readiness uses task_dependencies.
4. POST /internal/tasks/{task_id}/mark-displayed works.
5. mark-displayed validates queued or retrying status.
6. mark-displayed sets station_id, kds_task_id, displayed_at, status displayed.
7. POST /internal/tasks/{task_id}/start works.
8. start validates displayed status.
9. start validates station_id and kds_task_id.
10. start sets started_at, sla_deadline_at, status in_progress.
11. start updates order.status to cooking.
12. POST /internal/tasks/{task_id}/complete works.
13. complete validates in_progress status.
14. complete calculates actual_duration_seconds.
15. complete calculates delay_seconds.
16. complete sets task status done.
17. complete sets order.status ready_for_pickup when all tasks are done.
18. POST /internal/tasks/{task_id}/dispatch-failed works.
19. TaskDisplayed event is written.
20. TaskStarted event is written.
21. TaskCompleted event is written.
22. TaskDispatchFailed event is written.
23. OrderReadyForPickup event is written when applicable.
24. Invalid transitions return 409.
25. Unknown task returns 404.
26. Mongo event write failure does not fail the DB transition.
27. Tests pass.
28. No worker, Redis consumer, XACK, KDS delivery, station selection, retry loop, or DLQ is implemented.
```

---

## 20. Short instruction for the agent

Implement Stage 7 in services/fulfillment-service.

Add internal endpoints:

```text
GET /internal/tasks/{task_id}
GET /internal/tasks/{task_id}/dispatch-readiness
POST /internal/tasks/{task_id}/mark-displayed
POST /internal/tasks/{task_id}/start
POST /internal/tasks/{task_id}/complete
POST /internal/tasks/{task_id}/dispatch-failed
```

Implement status transitions:

```text
queued -> displayed
displayed -> in_progress
in_progress -> done
queued -> failed
retrying -> displayed
retrying -> failed
```

Use task_dependencies for dispatch-readiness.

Write MongoDB events:

```text
TaskDisplayed
TaskStarted
TaskCompleted
TaskDispatchFailed
OrderReadyForPickup
```

Do not implement:

```text
worker
Redis consumer
XREADGROUP
XACK
KDS delivery call
station selection
retry loop
DLQ
Kitchen Service claim endpoint
Kitchen Service complete endpoint
```
