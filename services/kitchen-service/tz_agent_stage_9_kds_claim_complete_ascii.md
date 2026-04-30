# Agent Task Spec: Stage 9 - KDS claim and complete in Kitchen Service

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

Stage 6:
  kitchen-service has local KDS state
  kds_station_tasks table
  internal KDS delivery endpoint
  dispatch candidates endpoint
  idempotent KDS delivery

Stage 7:
  fulfillment-service has internal task transition APIs
  task snapshot
  dispatch-readiness
  mark-displayed
  start
  complete
  dispatch-failed

Stage 8:
  kitchen-scheduler-worker reads Redis Streams
  dispatches queued tasks into KDS
  calls Fulfillment mark-displayed
```

This stage extends:

```text
services/kitchen-service
```

The goal is to implement station worker actions in KDS:

```text
claim
complete
```

KDS is local state inside Kitchen Service.
Fulfillment Service remains the only owner of global task business statuses.

---

## 1. Goal

Implement KDS claim and complete flow.

At the end of this stage:

```text
1. A station worker can claim a displayed KDS task.
2. Claim is protected against double claim.
3. Claim enforces station capacity.
4. Claim increments station.busy_slots.
5. Claim calls Fulfillment /internal/tasks/{task_id}/start.
6. A station worker can complete a claimed KDS task.
7. Complete calls Fulfillment /internal/tasks/{task_id}/complete.
8. Complete marks local KDS task as completed.
9. Complete decrements station.busy_slots.
10. MongoDB KDS and station events are written.
11. Tests prove double claim and capacity protection.
```

Stage boundary:

```text
This stage implements manual/API worker actions only.
This stage does not implement Station Simulator Service.
This stage does not implement simulated cooking sleep.
This stage does not implement Go worker changes.
```

---

## 2. Scope

Implement in Kitchen Service:

```text
1. POST /kds/stations/{station_id}/tasks/{task_id}/claim
2. POST /kds/stations/{station_id}/tasks/{task_id}/complete
3. Optional POST /kds/stations/{station_id}/tasks/{task_id}/fail
4. Fulfillment HTTP client:
   - POST /internal/tasks/{task_id}/start
   - POST /internal/tasks/{task_id}/complete
5. Atomic double-claim protection.
6. Atomic busy_slots < capacity check.
7. station.busy_slots increment on successful claim.
8. station.busy_slots decrement on successful complete.
9. KDS local status transitions:
   - displayed -> claimed
   - claimed -> completed
10. MongoDB events:
   - KdsTaskClaimed
   - KdsTaskClaimRejected
   - KdsTaskCompleted
   - StationBusySlotOccupied
   - StationBusySlotReleased
11. Unit and component tests.
12. README updates.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- Station Simulator Service
- simulator polling
- simulator sleep
- worker changes
- Redis consumer changes
- order creation changes
- Menu Service changes
- Fulfillment status transition implementation
- Prometheus metrics if not already present
- Grafana dashboards
- Kubernetes manifests
```

Do not write to Fulfillment database directly.

Do not read from Redis in Kitchen Service.

Kitchen Service must call Fulfillment Service through HTTP only.

---

## 4. Existing Kitchen Service behavior before this stage

Before Stage 9, Kitchen Service should already support:

```text
POST /kitchens
GET /kitchens
GET /kitchens/{kitchen_id}
POST /kitchens/{kitchen_id}/stations
GET /kitchens/{kitchen_id}/stations
PATCH /stations/{station_id}/capacity
PATCH /stations/{station_id}/status

GET /internal/kds/dispatch-candidates
POST /internal/kds/stations/{station_id}/tasks
GET /kds/stations/{station_id}/tasks
```

Existing local KDS task statuses:

```text
displayed
claimed
completed
failed
removed
```

Before this stage, only displayed was used by the delivery endpoint.

After this stage, use:

```text
displayed
claimed
completed
```

---

## 5. Dependencies

Kitchen Service should already have:

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

motor = "^3.4.0"
```

Add runtime dependency if missing:

```toml
httpx = "^0.27.0"
```

Dev dependencies:

```toml
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
httpx = "^0.27.0"
respx = "^0.21.0"
```

---

## 6. dk-common integration rule

Kitchen Service must continue using dk-common as a normal path dependency:

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

Do not put KDS domain logic or KDS events into dk-common.

Correct ownership:

```text
dk-common may contain infrastructure helpers.
kitchen-service owns KDS claim/complete logic and KDS event semantics.
```

---

## 7. Settings

Update services/kitchen-service/app/core/config.py.

Add Fulfillment Service settings:

```python
from functools import lru_cache

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "kitchen-service"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/kitchen_service"
    )

    fulfillment_service_url: str = "http://localhost:8003"
    http_timeout_seconds: float = 3.0

    mongo_url: str = "mongodb://localhost:27017"
    mongo_database: str = "dark_kitchen_events"
    mongo_events_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Environment variables:

```env
SERVICE_NAME=kitchen-service
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=readable

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kitchen_service

FULFILLMENT_SERVICE_URL=http://localhost:8003
HTTP_TIMEOUT_SECONDS=3

MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true
```

Docker env example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service
FULFILLMENT_SERVICE_URL=http://fulfillment-service:8000
MONGO_URL=mongodb://mongo:27017
MONGO_DATABASE=dark_kitchen_events
LOG_FORMAT=json
```

---

## 8. Data model review

Stage 6 should already have:

### 8.1. stations

Required fields:

```text
id
kitchen_id
station_type
name
capacity
busy_slots
visible_backlog_limit
status
created_at
updated_at
```

For Stage 9:

```text
busy_slots is incremented on claim.
busy_slots is decremented on complete.
busy_slots must never be less than 0.
busy_slots must never exceed capacity.
```

### 8.2. kds_station_tasks

Required fields:

```text
id
task_id
order_id
kitchen_id
station_id
station_type
operation
menu_item_name
status
estimated_duration_seconds
pickup_deadline
displayed_at
claimed_by
claimed_at
completed_at
idempotency_key
created_at
updated_at
```

For Stage 9:

```text
claim sets:
  status = claimed
  claimed_by = station_worker_id
  claimed_at = now or request timestamp

complete sets:
  status = completed
  completed_at = now or request timestamp
```

### 8.3. Alembic changes

If Stage 6 table already has claimed_by, claimed_at, completed_at, no migration is needed.

If missing, add migration:

```text
add claimed_by to kds_station_tasks
add claimed_at to kds_station_tasks
add completed_at to kds_station_tasks
```

Recommended constraints or indexes:

```text
INDEX(kds_station_tasks.station_id, status)
INDEX(kds_station_tasks.task_id)
INDEX(kds_station_tasks.claimed_by)
CHECK stations.busy_slots >= 0
CHECK stations.capacity > 0
CHECK stations.busy_slots <= stations.capacity
```

If DB-level busy_slots <= capacity check is hard because capacity can change, enforce in transactional service logic at minimum.

---

## 9. Fulfillment HTTP client

Create or extend:

```text
app/clients/fulfillment.py
```

Use httpx.AsyncClient.

The client must call:

```http
POST /internal/tasks/{task_id}/start
POST /internal/tasks/{task_id}/complete
```

### 9.1. POST /internal/tasks/{task_id}/start

Request body:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "station_worker_id": "grill-worker-1",
  "started_at": "2026-04-30T10:02:00Z"
}
```

Expected success:

```text
2xx
```

If Fulfillment returns 409:

```text
Convert to fulfillment_start_rejected.
```

If Fulfillment times out or returns 5xx:

```text
Convert to fulfillment_service_unavailable.
```

### 9.2. POST /internal/tasks/{task_id}/complete

Request body:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "station_worker_id": "grill-worker-1",
  "completed_at": "2026-04-30T10:08:00Z"
}
```

Expected success:

```text
2xx
```

If Fulfillment returns 409:

```text
Convert to fulfillment_complete_rejected.
```

If Fulfillment times out or returns 5xx:

```text
Convert to fulfillment_service_unavailable.
```

### 9.3. Correlation headers

Propagate:

```http
X-Correlation-ID
X-Request-ID
```

If dk-common exposes get_correlation_id and get_request_id, use them.

If not available, pass headers from request context explicitly.

---

## 10. API endpoints

Create or extend:

```text
app/api/routes/kds.py
```

---

### 10.1. POST /kds/stations/{station_id}/tasks/{task_id}/claim

Purpose:

```text
Station worker claims a displayed KDS task.
```

Request:

```json
{
  "station_worker_id": "grill-worker-1"
}
```

Optional request fields:

```json
{
  "station_worker_id": "grill-worker-1",
  "claimed_at": "2026-04-30T10:02:00Z"
}
```

Validation:

```text
station_id path param is required.
task_id path param is required.
station_worker_id is required and non-empty.
station must exist.
kds_station_task must exist by task_id.
kds_station_task.station_id must match path station_id.
kds_station_task.status must be displayed.
station.busy_slots must be less than station.capacity.
station.status should be available.
```

Processing:

```text
1. Start DB transaction.
2. Lock station row with SELECT FOR UPDATE.
3. Lock kds_station_task row with SELECT FOR UPDATE.
4. Validate station and task.
5. Validate kds_station_task.status = displayed.
6. Validate station.busy_slots < station.capacity.
7. Set kds_station_task.status = claimed.
8. Set kds_station_task.claimed_by = station_worker_id.
9. Set kds_station_task.claimed_at = claimed_at or now.
10. Increment station.busy_slots by 1.
11. Commit DB transaction.
12. Call Fulfillment /internal/tasks/{task_id}/start.
13. If Fulfillment call succeeds:
    - return 200.
14. If Fulfillment call fails:
    - MVP behavior: compensate local claim.
```

MVP compensation behavior for /start failure:

```text
If Fulfillment /start fails after local claim commit:
  1. Start new DB transaction.
  2. If task is still claimed by the same worker:
     - set task.status back to displayed.
     - clear claimed_by.
     - clear claimed_at.
     - decrement busy_slots by 1, not below 0.
  3. Write KdsTaskClaimRejected event.
  4. Return 503 or mapped error.
```

Alternative acceptable MVP behavior:

```text
Call Fulfillment /start before committing local claim.
```

But this is less safe because local and remote states can diverge under concurrency.
Preferred approach for this stage:

```text
Commit local claim first, then call Fulfillment /start, then compensate if /start fails.
```

Success response:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "claimed",
  "claimed_by": "grill-worker-1",
  "claimed_at": "2026-04-30T10:02:00Z"
}
```

Errors:

Task already claimed:

```http
409 Conflict
```

```json
{
  "error": "task_already_claimed",
  "message": "Task is already claimed"
}
```

Capacity exceeded:

```http
409 Conflict
```

```json
{
  "error": "station_capacity_exceeded",
  "message": "Station capacity is exceeded"
}
```

Station not found:

```http
404 Not Found
```

```json
{
  "error": "station_not_found",
  "message": "Station not found"
}
```

KDS task not found:

```http
404 Not Found
```

```json
{
  "error": "kds_task_not_found",
  "message": "KDS task not found"
}
```

Fulfillment unavailable:

```http
503 Service Unavailable
```

```json
{
  "error": "fulfillment_service_unavailable",
  "message": "Fulfillment Service is unavailable"
}
```

---

### 10.2. POST /kds/stations/{station_id}/tasks/{task_id}/complete

Purpose:

```text
Station worker completes a claimed KDS task.
```

Request:

```json
{
  "station_worker_id": "grill-worker-1"
}
```

Optional request fields:

```json
{
  "station_worker_id": "grill-worker-1",
  "completed_at": "2026-04-30T10:08:00Z"
}
```

Validation:

```text
station_id path param is required.
task_id path param is required.
station_worker_id is required and non-empty.
station must exist.
kds_station_task must exist by task_id.
kds_station_task.station_id must match path station_id.
kds_station_task.status must be claimed.
kds_station_task.claimed_by must match station_worker_id.
```

Processing:

Recommended MVP flow:

```text
1. Start DB transaction.
2. Lock station row with SELECT FOR UPDATE.
3. Lock kds_station_task row with SELECT FOR UPDATE.
4. Validate station and task.
5. Validate task.status = claimed.
6. Validate claimed_by = station_worker_id.
7. Commit or keep transaction short.
8. Call Fulfillment /internal/tasks/{task_id}/complete.
9. If Fulfillment call succeeds:
   - Start DB transaction.
   - Lock station and task again.
   - Set task.status = completed.
   - Set completed_at = completed_at or now.
   - Decrement station.busy_slots by 1, not below 0.
   - Commit.
   - Write events.
   - Return 200.
10. If Fulfillment call fails:
   - Do not mark local task completed.
   - Do not release busy slot.
   - Return 503 or mapped error.
```

Reason:

```text
For MVP, if Fulfillment /complete fails, keep local task claimed.
This allows the worker or user to retry complete later.
```

Success response:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "completed",
  "claimed_by": "grill-worker-1",
  "completed_at": "2026-04-30T10:08:00Z"
}
```

Errors:

Task not claimed:

```http
409 Conflict
```

```json
{
  "error": "task_not_claimed",
  "message": "Task is not claimed"
}
```

Wrong worker:

```http
409 Conflict
```

```json
{
  "error": "task_claimed_by_another_worker",
  "message": "Task is claimed by another worker"
}
```

Fulfillment unavailable:

```http
503 Service Unavailable
```

```json
{
  "error": "fulfillment_service_unavailable",
  "message": "Fulfillment Service is unavailable"
}
```

---

### 10.3. Optional POST /kds/stations/{station_id}/tasks/{task_id}/fail

This endpoint is optional in Stage 9.

If implemented, keep it minimal.

Purpose:

```text
Station worker marks a claimed or displayed KDS task as failed.
```

Request:

```json
{
  "station_worker_id": "grill-worker-1",
  "reason": "station_error"
}
```

MVP behavior:

```text
1. Validate task exists.
2. Validate station_id matches.
3. If task is claimed, require claimed_by = station_worker_id.
4. Set local status = failed.
5. If task was claimed, decrement busy_slots by 1.
6. Write KdsTaskFailed event.
```

Do not call Fulfillment /fail unless Stage 7 already implemented and the project is ready to wire it.
This endpoint is not required for Definition of Done.

---

## 11. Atomicity and concurrency

### 11.1. Double claim protection

Double claim must be impossible.

Use DB row locks:

```text
SELECT station FOR UPDATE
SELECT kds_station_task FOR UPDATE
```

Or use atomic UPDATE with conditions.

Recommended transaction:

```sql
BEGIN;

SELECT *
FROM stations
WHERE id = :station_id
FOR UPDATE;

SELECT *
FROM kds_station_tasks
WHERE task_id = :task_id
  AND station_id = :station_id
FOR UPDATE;

-- validate station.busy_slots < station.capacity
-- validate task.status = 'displayed'

UPDATE kds_station_tasks
SET status = 'claimed',
    claimed_by = :station_worker_id,
    claimed_at = now(),
    updated_at = now()
WHERE task_id = :task_id
  AND station_id = :station_id
  AND status = 'displayed';

UPDATE stations
SET busy_slots = busy_slots + 1,
    updated_at = now()
WHERE id = :station_id
  AND busy_slots < capacity;

COMMIT;
```

If affected rows = 0:

```text
return 409
```

### 11.2. Capacity protection

Capacity must be enforced at claim time.

Rules:

```text
busy_slots < capacity is required before claim.
busy_slots increments only on successful local claim.
busy_slots decrements only on successful complete or claim compensation.
busy_slots must never become negative.
busy_slots must never exceed capacity.
```

### 11.3. Complete concurrency

Two complete calls for the same task must not double-release capacity.

Use row locks or conditional update:

```text
Only transition claimed -> completed once.
Only decrement busy_slots if task was actually transitioned to completed.
```

If task is already completed:

```text
Return 200 only if idempotency is easy and same worker.
Otherwise return 409 task_already_completed.
```

MVP recommended:

```text
If already completed:
  return 409 task_already_completed
```

---

## 12. Fulfillment callback consistency

### 12.1. Claim and /start

Preferred MVP sequence:

```text
1. Commit local claim and busy slot increment.
2. Call Fulfillment /start.
3. If /start succeeds, return success.
4. If /start fails, compensate local claim and return error.
```

Compensation details:

```text
Only compensate if:
  kds_task.status = claimed
  kds_task.claimed_by = station_worker_id

Then:
  set status = displayed
  clear claimed_by
  clear claimed_at
  busy_slots = max(0, busy_slots - 1)
```

### 12.2. Complete and /complete

Preferred MVP sequence:

```text
1. Validate local task is claimed by worker.
2. Call Fulfillment /complete.
3. If /complete succeeds:
   - mark local task completed
   - release busy slot
4. If /complete fails:
   - leave local task claimed
   - do not release busy slot
   - return error
```

This is acceptable MVP behavior.

Future improvement:

```text
completion_pending local status
background retry
idempotency key for /complete
```

Do not implement background retry in this stage.

---

## 13. MongoDB events

Use existing Kitchen Service event writer from Stage 6 or add local event writer.

Collections:

```text
kds_events
station_events
```

Event write behavior:

```text
If MONGO_EVENTS_ENABLED=false:
  do not write events.

If MongoDB is temporarily unavailable:
  log the error.
  Do not fail claim or complete only because event write failed.
```

### 13.1. KdsTaskClaimed event

Write after successful claim and Fulfillment /start success.

```json
{
  "event_type": "KdsTaskClaimed",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "station_type": "grill",
  "station_worker_id": "grill-worker-1",
  "payload": {
    "claimed_at": "2026-04-30T10:02:00Z"
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:02:00Z"
}
```

### 13.2. KdsTaskClaimRejected event

Write when claim fails due to conflict or capacity.

```json
{
  "event_type": "KdsTaskClaimRejected",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "station_worker_id": "grill-worker-2",
  "payload": {
    "reason": "task_already_claimed"
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:02:01Z"
}
```

### 13.3. KdsTaskCompleted event

Write after successful complete and local completion.

```json
{
  "event_type": "KdsTaskCompleted",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "station_type": "grill",
  "station_worker_id": "grill-worker-1",
  "payload": {
    "completed_at": "2026-04-30T10:08:00Z"
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:08:00Z"
}
```

### 13.4. StationBusySlotOccupied event

Write after successful claim.

```json
{
  "event_type": "StationBusySlotOccupied",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "payload": {
    "busy_slots": 1,
    "capacity": 2
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:02:00Z"
}
```

### 13.5. StationBusySlotReleased event

Write after successful complete or claim compensation.

```json
{
  "event_type": "StationBusySlotReleased",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "payload": {
    "busy_slots": 0,
    "capacity": 2,
    "reason": "task_completed"
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:08:00Z"
}
```

---

## 14. Recommended code structure

Add or extend:

```text
services/kitchen-service/
  app/
    api/
      routes/
        kds.py
    clients/
      fulfillment.py
    domain/
      kds_statuses.py
      errors.py
    events/
      kds_events.py
      station_events.py
    repositories/
      kds.py
      stations.py
    schemas/
      kds.py
    services/
      kds_claim.py
      kds_complete.py
```

Preferred flow:

```text
routes -> service layer -> repositories -> SQLAlchemy
service layer -> Fulfillment HTTP client
service layer -> Mongo event writer
```

Do not put claim/complete transaction logic directly in route handlers.

---

## 15. Pydantic schemas

Extend app/schemas/kds.py.

### 15.1. KdsTaskClaimRequest

Fields:

```text
station_worker_id str
claimed_at datetime or None
```

Validation:

```text
station_worker_id required
station_worker_id non-empty
```

### 15.2. KdsTaskClaimResponse

Fields:

```text
kds_task_id UUID
task_id UUID
station_id UUID
status str
claimed_by str
claimed_at datetime
```

### 15.3. KdsTaskCompleteRequest

Fields:

```text
station_worker_id str
completed_at datetime or None
```

Validation:

```text
station_worker_id required
station_worker_id non-empty
```

### 15.4. KdsTaskCompleteResponse

Fields:

```text
kds_task_id UUID
task_id UUID
station_id UUID
status str
claimed_by str
completed_at datetime
```

---

## 16. API errors

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
station_not_found
station_not_available
kds_task_not_found
kds_task_station_mismatch
task_already_claimed
task_not_displayed
station_capacity_exceeded
task_not_claimed
task_claimed_by_another_worker
task_already_completed
fulfillment_start_rejected
fulfillment_complete_rejected
fulfillment_service_unavailable
validation_error
internal_error
```

Recommended mappings:

```text
station_not_found -> 404
kds_task_not_found -> 404
station_not_available -> 409
kds_task_station_mismatch -> 409
task_already_claimed -> 409
task_not_displayed -> 409
station_capacity_exceeded -> 409
task_not_claimed -> 409
task_claimed_by_another_worker -> 409
task_already_completed -> 409
fulfillment_start_rejected -> 409
fulfillment_complete_rejected -> 409
fulfillment_service_unavailable -> 503
validation_error -> 422
internal_error -> 500
```

Do not put KDS domain errors into dk-common.

---

## 17. Tests

### 17.1. Test command

Tests must run from services/kitchen-service:

```bash
poetry run pytest
```

### 17.2. Required tests

#### test_kds_claim_success.py

Check:

```text
displayed task can be claimed
claim sets status = claimed
claim sets claimed_by
claim sets claimed_at
claim increments station.busy_slots by 1
claim calls Fulfillment /start with station_id, kds_task_id, station_worker_id, started_at
KdsTaskClaimed event is written
StationBusySlotOccupied event is written
```

#### test_kds_double_claim.py

Check:

```text
Given one displayed KDS task
When two workers claim it concurrently
Then one request returns 200
And the other returns 409 task_already_claimed
And only one worker is saved in claimed_by
And station.busy_slots increments only once
And Fulfillment /start is called only once
```

Use asyncio.gather or parallel test clients if possible.

If true concurrent test is hard, test with sequential duplicate claims plus repository-level atomic update.

#### test_kds_capacity.py

Check:

```text
Given station.capacity = 1
And station.busy_slots = 0
And two displayed tasks on the same station
When two claim requests happen concurrently for different tasks
Then only one claim succeeds
And one claim returns 409 station_capacity_exceeded
And busy_slots never exceeds 1
```

#### test_kds_claim_validation.py

Check:

```text
unknown station returns 404
unknown KDS task returns 404
task for another station returns 409
non-displayed task returns 409
unavailable station returns 409
missing station_worker_id returns 422
```

#### test_kds_claim_fulfillment_failure.py

Check:

```text
If local claim succeeds but Fulfillment /start fails:
  API returns 503 or mapped error
  local task returns to displayed
  claimed_by is cleared
  claimed_at is cleared
  busy_slots is decremented back
  KdsTaskClaimRejected event is written
```

#### test_kds_complete_success.py

Check:

```text
claimed task can be completed by same worker
complete calls Fulfillment /complete
local task becomes completed
completed_at is set
busy_slots decrements by 1
KdsTaskCompleted event is written
StationBusySlotReleased event is written
```

#### test_kds_complete_validation.py

Check:

```text
unknown station returns 404
unknown KDS task returns 404
task for another station returns 409
displayed task cannot be completed
completed task cannot be completed again
wrong station_worker_id returns 409 task_claimed_by_another_worker
missing station_worker_id returns 422
```

#### test_kds_complete_fulfillment_failure.py

Check:

```text
If Fulfillment /complete fails:
  API returns 503 or mapped error
  local task remains claimed
  busy_slots is not released
  completed_at remains null
```

#### test_kds_busy_slots_invariants.py

Check:

```text
busy_slots never goes below 0
busy_slots never exceeds capacity
complete releases exactly one slot
claim compensation releases exactly one slot
```

#### test_no_simulator.py

Check by route list or code review:

```text
station-simulator-service is not implemented in this stage
no simulated cooking sleep exists in Kitchen Service
```

---

## 18. Manual test scenario

Add to README.

Prerequisites:

```text
1. Start kitchen-service.
2. Start fulfillment-service.
3. Create kitchen.
4. Create station with capacity = 1.
5. Deliver a task to KDS through Stage 6 endpoint.
6. Ensure Fulfillment task is displayed.
```

### 18.1. Claim task

```bash
curl -X POST http://localhost:8000/kds/stations/{station_id}/tasks/{task_id}/claim \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-claim-1" \
  -d '{
    "station_worker_id": "grill-worker-1"
  }'
```

Expected:

```text
200 OK
status = claimed
claimed_by = grill-worker-1
station.busy_slots increased by 1
Fulfillment task status becomes in_progress
```

### 18.2. Try duplicate claim

```bash
curl -X POST http://localhost:8000/kds/stations/{station_id}/tasks/{task_id}/claim \
  -H "Content-Type: application/json" \
  -d '{
    "station_worker_id": "grill-worker-2"
  }'
```

Expected:

```text
409 Conflict
error = task_already_claimed
```

### 18.3. Complete task

```bash
curl -X POST http://localhost:8000/kds/stations/{station_id}/tasks/{task_id}/complete \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-complete-1" \
  -d '{
    "station_worker_id": "grill-worker-1"
  }'
```

Expected:

```text
200 OK
status = completed
station.busy_slots decreased by 1
Fulfillment task status becomes done
```

### 18.4. Complete by wrong worker

```bash
curl -X POST http://localhost:8000/kds/stations/{station_id}/tasks/{task_id}/complete \
  -H "Content-Type: application/json" \
  -d '{
    "station_worker_id": "grill-worker-2"
  }'
```

Expected if task is still claimed by grill-worker-1:

```text
409 Conflict
error = task_claimed_by_another_worker
```

---

## 19. README updates

Update services/kitchen-service/README.md.

Add:

```text
1. KDS claim/complete section.
2. Status transitions:
   - displayed -> claimed
   - claimed -> completed
3. Capacity rule:
   - busy_slots < capacity at claim time
4. Double claim protection explanation.
5. Fulfillment callback behavior.
6. Compensation behavior if /start fails.
7. Behavior if /complete fails.
8. Manual curl examples.
9. Stage boundary:
   - Station Simulator is not implemented yet.
```

Example commands:

```bash
cd services/kitchen-service

poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
poetry run pytest
```

---

## 20. Definition of Done

Stage is complete when:

```text
1. POST /kds/stations/{station_id}/tasks/{task_id}/claim exists.
2. POST /kds/stations/{station_id}/tasks/{task_id}/complete exists.
3. Claim validates station exists.
4. Claim validates KDS task exists.
5. Claim validates task belongs to station.
6. Claim validates task status = displayed.
7. Claim validates station.busy_slots < station.capacity.
8. Claim is atomic under concurrent requests.
9. Double claim is impossible.
10. Claim increments busy_slots exactly once.
11. Claim sets local task status = claimed.
12. Claim sets claimed_by and claimed_at.
13. Claim calls Fulfillment /internal/tasks/{task_id}/start.
14. Claim compensation works if Fulfillment /start fails.
15. Complete validates station exists.
16. Complete validates KDS task exists.
17. Complete validates task belongs to station.
18. Complete validates task status = claimed.
19. Complete validates claimed_by = station_worker_id.
20. Complete calls Fulfillment /internal/tasks/{task_id}/complete.
21. Complete sets local task status = completed only after Fulfillment /complete succeeds.
22. Complete sets completed_at.
23. Complete decrements busy_slots exactly once.
24. Complete does not release busy slot if Fulfillment /complete fails.
25. KdsTaskClaimed event is written.
26. KdsTaskClaimRejected event is written for rejected claims or compensation.
27. KdsTaskCompleted event is written.
28. StationBusySlotOccupied event is written.
29. StationBusySlotReleased event is written.
30. Tests cover double claim.
31. Tests cover capacity.
32. Tests cover Fulfillment callback failure behavior.
33. No Station Simulator is implemented.
34. No Redis consumer or worker logic is added to Kitchen Service.
```

---

## 21. Short instruction for the agent

Implement Stage 9 in services/kitchen-service.

Add:

```text
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
Fulfillment HTTP client
atomic double-claim protection
atomic capacity check
busy_slots increment on claim
busy_slots release on complete
MongoDB KDS and station events
tests
README updates
```

Critical rules:

```text
Only displayed tasks can be claimed.
Only claimed tasks can be completed.
Only the worker who claimed a task can complete it.
busy_slots must never exceed capacity.
busy_slots must never go below 0.
Fulfillment /start must be called after claim.
Fulfillment /complete must be called before local complete is finalized.
```

Do not implement:

```text
Station Simulator Service
simulated cooking sleep
Go worker changes
Redis consumer changes
direct Fulfillment DB access
```
