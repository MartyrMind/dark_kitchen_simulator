# Agent Task Spec: Stage 6 - KDS inside Kitchen Service

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
  POST /orders creates kitchen_tasks

Stage 5:
  fulfillment-service publishes kitchen_tasks to Redis Streams
  kitchen_tasks move from created to queued
  TaskQueued event is written to MongoDB
```

This stage extends:

```text
services/kitchen-service
```

The goal is to implement local KDS state inside Kitchen Service.

KDS means Kitchen Display System.
It stores the task list visible on a station screen.

---

## 1. Goal

Implement KDS inside Kitchen Service without claim/complete flow.

At the end of this stage:

```text
1. Kitchen Service has kds_station_tasks table.
2. A dispatcher can ask for dispatch candidates.
3. A dispatcher can deliver a task to a concrete station.
4. Delivered task is stored as local KDS task with status = displayed.
5. Delivery is idempotent by idempotency_key.
6. GET /kds/stations/{station_id}/tasks returns visible tasks for the station.
7. KdsTaskDisplayed event is written to MongoDB.
```

Stage boundary:

```text
This stage stores displayed tasks in KDS.
This stage does not implement claim.
This stage does not implement complete.
This stage does not call Fulfillment mark-displayed.
This stage does not consume Redis.
This stage does not implement the Go worker.
```

---

## 2. Scope

Implement in Kitchen Service:

```text
1. SQLAlchemy model kds_station_tasks.
2. Alembic migration for kds_station_tasks.
3. Pydantic schemas for KDS delivery and KDS task responses.
4. Repository/service layer for KDS.
5. Internal API:
   - GET /internal/kds/dispatch-candidates
   - POST /internal/kds/stations/{station_id}/tasks
6. Public KDS read API:
   - GET /kds/stations/{station_id}/tasks
7. Idempotency by idempotency_key.
8. Unique constraints:
   - UNIQUE(task_id)
   - UNIQUE(idempotency_key)
9. KdsTaskDisplayed MongoDB event.
10. Tests for dispatch candidates, idempotency, visible backlog, and station task listing.
11. README updates.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- POST /kds/stations/{station_id}/tasks/{task_id}/claim
- POST /kds/stations/{station_id}/tasks/{task_id}/complete
- POST /kds/stations/{station_id}/tasks/{task_id}/fail
- station busy_slots increment
- station busy_slots release
- capacity check during claim
- Fulfillment Service callback
- POST /internal/tasks/{task_id}/mark-displayed
- POST /internal/tasks/{task_id}/start
- POST /internal/tasks/{task_id}/complete
- Redis consumer
- Kitchen Scheduler Worker
- retry/backoff/DLQ
- Prometheus metrics
- full MongoDB event log system
```

Important:

```text
Capacity is not consumed during dispatch.
Capacity is consumed later during claim.
This stage only controls visible_backlog_limit.
```

---

## 4. Existing Kitchen Service behavior before this stage

Before Stage 6, Kitchen Service should already support:

```text
POST /kitchens
GET /kitchens
GET /kitchens/{kitchen_id}
POST /kitchens/{kitchen_id}/stations
GET /kitchens/{kitchen_id}/stations
PATCH /stations/{station_id}/capacity
PATCH /stations/{station_id}/status
```

Existing models:

```text
kitchens
stations
```

Existing station fields should include:

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

Allowed station status values:

```text
available
unavailable
maintenance
```

---

## 5. Dependencies

Update services/kitchen-service/pyproject.toml if needed.

Runtime dependencies to add for this stage:

```toml
motor = "^3.4.0"
```

Keep existing dependencies:

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
```

Dev dependencies can include:

```toml
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
httpx = "^0.27.0"
```

Do not add Redis dependency in this stage.

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

If dk-common already has a generic Mongo event helper, it may be used.
If not, implement a local Kitchen Service Mongo event writer.

Do not put Kitchen/KDS domain events into dk-common.

Correct ownership:

```text
dk-common may know how to write generic infrastructure events.
kitchen-service owns the KdsTaskDisplayed event shape and semantics.
```

---

## 7. Settings

Update services/kitchen-service/app/core/config.py.

Add Mongo settings:

```python
from functools import lru_cache

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "kitchen-service"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/kitchen_service"
    )

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

MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true
```

Docker env example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service
MONGO_URL=mongodb://mongo:27017
MONGO_DATABASE=dark_kitchen_events
LOG_FORMAT=json
```

---

## 8. Database model

### 8.1. kds_station_tasks

Add table:

```text
kds_station_tasks
```

Fields:

```text
id                            UUID primary key
task_id                       UUID, required
order_id                      UUID, required
kitchen_id                    UUID, required
station_id                    UUID, required, foreign key to stations.id
station_type                  string, required
operation                     string, required
menu_item_name                string, nullable
status                        string, required
estimated_duration_seconds    integer, required
pickup_deadline               timestamp with timezone, nullable
displayed_at                  timestamp with timezone, required
claimed_by                    string, nullable
claimed_at                    timestamp with timezone, nullable
completed_at                  timestamp with timezone, nullable
idempotency_key               string, required
created_at                    timestamp with timezone
updated_at                    timestamp with timezone
```

Local KDS statuses:

```text
displayed
claimed
completed
failed
removed
```

For this stage, only use:

```text
displayed
```

Constraints:

```text
UNIQUE(task_id)
UNIQUE(idempotency_key)
estimated_duration_seconds > 0
status not null
```

Indexes:

```text
INDEX(station_id, status)
INDEX(kitchen_id, station_type)
INDEX(task_id)
INDEX(idempotency_key)
```

Important ownership rule:

```text
task_id is an external reference to Fulfillment Service kitchen_tasks.id.
order_id is an external reference to Fulfillment Service orders.id.
Do not create database foreign keys to Fulfillment Service tables.
```

Only station_id may be a local FK:

```text
kds_station_tasks.station_id -> stations.id
```

### 8.2. Alembic migration

Create a migration:

```bash
cd services/kitchen-service
poetry run alembic revision --autogenerate -m "add kds station tasks"
poetry run alembic upgrade head
```

The migration must create:

```text
kds_station_tasks
```

with constraints:

```text
primary key id
foreign key station_id to stations.id
unique task_id
unique idempotency_key
check estimated_duration_seconds > 0
indexes for station_id/status and kitchen_id/station_type
```

No foreign keys to Fulfillment Service.

---

## 9. API endpoints

### 9.1. GET /internal/kds/dispatch-candidates

Internal endpoint used by the future Kitchen Scheduler Worker.

Path:

```http
GET /internal/kds/dispatch-candidates?kitchen_id={kitchen_id}&station_type={station_type}
```

Purpose:

```text
Return stations that can receive another displayed KDS task.
```

Query params:

```text
kitchen_id required UUID
station_type required string
```

Candidate rules:

```text
1. station.kitchen_id must match kitchen_id.
2. station.station_type must match station_type.
3. station.status must be available.
4. visible_backlog_size must be less than visible_backlog_limit.
5. health should be ok for MVP.
```

Visible backlog size:

```text
Count kds_station_tasks for this station where status is displayed.
```

Future-proof alternative:

```text
Count statuses displayed and claimed as visible backlog.
```

For Stage 6 use:

```text
displayed only
```

Response:

```json
[
  {
    "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "station_type": "grill",
    "status": "available",
    "capacity": 2,
    "busy_slots": 0,
    "visible_backlog_size": 1,
    "visible_backlog_limit": 4,
    "health": "ok"
  }
]
```

If no candidates:

```json
[]
```

Do not return unavailable or maintenance stations.

Do not consume busy_slots here.

### 9.2. POST /internal/kds/stations/{station_id}/tasks

Internal endpoint used by the future Kitchen Scheduler Worker.

Path:

```http
POST /internal/kds/stations/{station_id}/tasks
```

Purpose:

```text
Deliver a queued Fulfillment task to the KDS of a concrete station.
```

Request:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "operation": "cook_patty",
  "menu_item_name": "Burger",
  "estimated_duration_seconds": 480,
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "idempotency_key": "8f39f9fc-9c17-4995-8767-fd7e62c44852:dispatch:v1"
}
```

Validation:

```text
station_id path param is required
station must exist
station.status must be available
request.kitchen_id must match station.kitchen_id
request.station_type must match station.station_type
estimated_duration_seconds > 0
idempotency_key required
```

Visible backlog rule:

```text
If current visible_backlog_size >= station.visible_backlog_limit:
  return 409 visible_backlog_limit_exceeded
```

Successful response: 201 Created

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "displayed"
}
```

Idempotent response: 200 OK

If the same idempotency_key was already used, return the existing task:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "displayed"
}
```

Idempotency rule:

```text
Repeated POST with the same idempotency_key must not create a duplicate row.
It must return the already created KDS task.
```

Task duplicate rule:

```text
If task_id already exists with a different idempotency_key:
  return 409 kds_task_already_exists
```

The endpoint must not:

```text
- call Fulfillment Service
- mark task displayed in Fulfillment
- change station.busy_slots
- consume capacity
```

### 9.3. GET /kds/stations/{station_id}/tasks

Public KDS read endpoint for station screen.

Path:

```http
GET /kds/stations/{station_id}/tasks
```

Purpose:

```text
Return visible tasks displayed on the station.
```

Query params:

```text
status optional, default displayed
limit optional, default 100
offset optional, default 0
```

For Stage 6, default should return status = displayed only.

Response:

```json
[
  {
    "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
    "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
    "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
    "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "operation": "cook_patty",
    "menu_item_name": "Burger",
    "status": "displayed",
    "estimated_duration_seconds": 480,
    "pickup_deadline": "2026-04-30T18:45:00Z",
    "displayed_at": "2026-04-30T10:00:01Z"
  }
]
```

Ordering:

```text
displayed_at ASC
created_at ASC
```

If station does not exist:

```http
404 Not Found
```

---

## 10. MongoDB KdsTaskDisplayed event

### 10.1. Requirement

Write a minimal KdsTaskDisplayed event to MongoDB when a new KDS task is created.

Collection:

```text
kds_events
```

Event shape:

```json
{
  "event_type": "KdsTaskDisplayed",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "station_type": "grill",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "payload": {
    "operation": "cook_patty",
    "menu_item_name": "Burger",
    "estimated_duration_seconds": 480,
    "idempotency_key": "8f39f9fc-9c17-4995-8767-fd7e62c44852:dispatch:v1"
  },
  "correlation_id": "corr_123",
  "service": "kitchen-service",
  "created_at": "2026-04-30T10:00:01Z"
}
```

### 10.2. Event write behavior

Behavior:

```text
If MONGO_EVENTS_ENABLED=false:
  do not write events.

If MongoDB is temporarily unavailable:
  log the error.
  Do not fail KDS delivery only because the event write failed.
```

Important:

```text
KDS task creation is part of core flow.
Mongo event is diagnostic/audit.
```

### 10.3. Idempotency and event write

For repeated idempotent POST with the same idempotency_key:

```text
Do not create another kds_station_tasks row.
Do not write duplicate KdsTaskDisplayed event if avoidable.
Return the existing KDS task.
```

If preventing duplicate event is complex, it is acceptable for MVP to log no event on idempotent replay by detecting existing row before insertion.

---

## 11. Recommended code structure

Add or extend:

```text
services/kitchen-service/
  app/
    api/
      routes/
        internal_kds.py
        kds.py
    events/
      __init__.py
      mongo.py
      kds_events.py
    models/
      kds_station_task.py
    schemas/
      kds.py
    repositories/
      kds.py
    services/
      kds.py
```

Router recommendation:

```text
app.include_router(internal_kds.router)
app.include_router(kds.router)
```

Suggested route prefixes:

```text
internal_kds.router:
  no global prefix or prefix="/internal/kds"

kds.router:
  prefix="/kds"
```

Keep route handlers thin.

Preferred flow:

```text
routes -> service layer -> repository layer -> SQLAlchemy
service layer -> Mongo event writer
```

---

## 12. Pydantic schemas

Create app/schemas/kds.py.

### 12.1. KdsTaskDeliveryRequest

Fields:

```text
task_id UUID
order_id UUID
kitchen_id UUID
station_type str
operation str
menu_item_name str or None
estimated_duration_seconds int > 0
pickup_deadline datetime or None
idempotency_key str
```

Validation:

```text
operation non-empty
station_type non-empty
idempotency_key non-empty
estimated_duration_seconds > 0
```

### 12.2. KdsTaskDeliveryResponse

Fields:

```text
kds_task_id UUID
task_id UUID
station_id UUID
status str
```

### 12.3. DispatchCandidateResponse

Fields:

```text
station_id UUID
station_type str
status str
capacity int
busy_slots int
visible_backlog_size int
visible_backlog_limit int
health str
```

### 12.4. KdsStationTaskResponse

Fields:

```text
kds_task_id UUID
task_id UUID
order_id UUID
station_id UUID
operation str
menu_item_name str or None
status str
estimated_duration_seconds int
pickup_deadline datetime or None
displayed_at datetime
```

---

## 13. API errors

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
station_type_mismatch
station_kitchen_mismatch
visible_backlog_limit_exceeded
kds_task_already_exists
invalid_kds_task_status
validation_error
internal_error
```

Recommended mappings:

```text
station_not_found -> 404
station_not_available -> 409
station_type_mismatch -> 409
station_kitchen_mismatch -> 409
visible_backlog_limit_exceeded -> 409
kds_task_already_exists -> 409
validation_error -> 422
internal_error -> 500
```

Do not put KDS domain errors into dk-common.

Correct ownership:

```text
Infrastructure errors can live in dk-common.
KDS domain errors must live in kitchen-service.
```

---

## 14. Concurrency and idempotency

The delivery endpoint must be safe under concurrent duplicate requests.

Required guarantees:

```text
1. Two concurrent requests with the same idempotency_key create only one row.
2. Two concurrent requests with the same task_id create only one row.
3. Repeated request with same idempotency_key returns the existing row.
4. Repeated request with same task_id but different idempotency_key returns conflict.
```

Implementation hints:

```text
Use unique constraints in DB.
Catch IntegrityError.
After IntegrityError, query by idempotency_key.
If found, return existing row.
Otherwise query by task_id and return conflict.
```

Backlog limit concurrency:

```text
For MVP, a simple count before insert is acceptable.
For stricter behavior, lock station row with SELECT FOR UPDATE before counting and inserting.
```

Recommended MVP transaction:

```text
BEGIN
SELECT station FOR UPDATE
validate station
count visible backlog
if limit exceeded -> 409
insert kds_station_tasks
COMMIT
```

Do not modify station.busy_slots in this transaction.

---

## 15. Tests

### 15.1. Test command

Tests must run from services/kitchen-service:

```bash
poetry run pytest
```

### 15.2. Required tests

#### test_dispatch_candidates.py

Check:

```text
available station is returned as candidate
unavailable station is not returned
maintenance station is not returned
station with wrong station_type is not returned
station with visible_backlog_size >= visible_backlog_limit is not returned
visible_backlog_size is calculated from displayed KDS tasks
```

#### test_kds_delivery.py

Check:

```text
POST /internal/kds/stations/{station_id}/tasks creates KDS task
created KDS task has status displayed
response contains kds_task_id, task_id, station_id, status
GET /kds/stations/{station_id}/tasks returns delivered task
station.busy_slots does not change after delivery
```

#### test_kds_delivery_validation.py

Check:

```text
unknown station returns 404
unavailable station returns 409
kitchen_id mismatch returns 409
station_type mismatch returns 409
visible backlog limit exceeded returns 409
estimated_duration_seconds <= 0 returns 422
missing idempotency_key returns 422
```

#### test_kds_idempotency.py

Check:

```text
same idempotency_key repeated returns same kds_task_id
same idempotency_key repeated does not create duplicate row
same task_id with different idempotency_key returns 409
concurrent duplicate delivery creates only one row if feasible
```

#### test_kds_events.py

With fake Mongo event writer, check:

```text
KdsTaskDisplayed event is written after new delivery
event contains event_type = KdsTaskDisplayed
event contains task_id, order_id, kitchen_id, station_id, station_type
event contains kds_task_id
event contains idempotency_key in payload
```

Also check:

```text
If Mongo write fails:
  KDS delivery still succeeds
  error is logged
```

#### test_no_claim_complete.py

Check by route behavior or route list:

```text
claim endpoint is not implemented in this stage
complete endpoint is not implemented in this stage
delivery does not increment busy_slots
delivery does not call Fulfillment Service
```

---

## 16. Manual check scenario

Add to README.

### 16.1. Create kitchen and station

```bash
curl -X POST http://localhost:8000/kitchens \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Kitchen 1",
    "city": "London",
    "status": "active"
  }'
```

```bash
curl -X POST http://localhost:8000/kitchens/{kitchen_id}/stations \
  -H "Content-Type: application/json" \
  -d '{
    "station_type": "grill",
    "name": "Grill 1",
    "capacity": 2,
    "busy_slots": 0,
    "visible_backlog_limit": 4,
    "status": "available"
  }'
```

### 16.2. Get dispatch candidates

```bash
curl "http://localhost:8000/internal/kds/dispatch-candidates?kitchen_id={kitchen_id}&station_type=grill"
```

Expected:

```text
station is returned with visible_backlog_size = 0
```

### 16.3. Deliver task to KDS

```bash
curl -X POST http://localhost:8000/internal/kds/stations/{station_id}/tasks \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-manual-1" \
  -d '{
    "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
    "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
    "kitchen_id": "{kitchen_id}",
    "station_type": "grill",
    "operation": "cook_patty",
    "menu_item_name": "Burger",
    "estimated_duration_seconds": 480,
    "pickup_deadline": "2026-04-30T18:45:00Z",
    "idempotency_key": "8f39f9fc-9c17-4995-8767-fd7e62c44852:dispatch:v1"
  }'
```

Expected:

```text
201 Created
status = displayed
```

### 16.4. Repeat same delivery

Run the same command again.

Expected:

```text
200 OK
same kds_task_id
no duplicate DB row
```

### 16.5. Get station tasks

```bash
curl http://localhost:8000/kds/stations/{station_id}/tasks
```

Expected:

```text
the delivered task is returned
status = displayed
```

---

## 17. README updates

Update services/kitchen-service/README.md.

Add:

```text
1. KDS purpose.
2. Stage boundary: delivery only, no claim/complete yet.
3. New table kds_station_tasks.
4. MongoDB requirement for KdsTaskDisplayed events.
5. New env variables:
   - MONGO_URL
   - MONGO_DATABASE
   - MONGO_EVENTS_ENABLED
6. How to run migration.
7. How to test dispatch candidates.
8. How to test idempotent KDS delivery.
9. How to list station KDS tasks.
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

## 18. Docker Compose notes

If there is a compose file, add or verify:

```yaml
services:
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"

  kitchen-service:
    environment:
      MONGO_URL: mongodb://mongo:27017
      MONGO_DATABASE: dark_kitchen_events
      MONGO_EVENTS_ENABLED: "true"
```

Do not add Kitchen Scheduler Worker yet.

---

## 19. Definition of Done

Stage is complete when:

```text
1. Kitchen Service has kds_station_tasks model.
2. Alembic migration creates kds_station_tasks.
3. kds_station_tasks has UNIQUE(task_id).
4. kds_station_tasks has UNIQUE(idempotency_key).
5. GET /internal/kds/dispatch-candidates works.
6. Dispatch candidates filter by kitchen_id and station_type.
7. Dispatch candidates exclude unavailable and maintenance stations.
8. Dispatch candidates include visible_backlog_size.
9. Dispatch candidates exclude full visible backlog stations.
10. POST /internal/kds/stations/{station_id}/tasks creates displayed KDS task.
11. Repeated POST with same idempotency_key returns existing KDS task.
12. Repeated POST does not create duplicate row.
13. GET /kds/stations/{station_id}/tasks returns displayed station tasks.
14. KdsTaskDisplayed event is written to MongoDB on new delivery.
15. MongoDB failure does not fail KDS delivery.
16. station.busy_slots is not changed by delivery.
17. No claim endpoint is implemented.
18. No complete endpoint is implemented.
19. No Fulfillment callback is implemented.
20. No Redis consumer or worker logic is implemented.
21. Tests pass.
```

---

## 20. Short instruction for the agent

Implement Stage 6 in services/kitchen-service.

Add:

```text
kds_station_tasks model
Alembic migration
GET /internal/kds/dispatch-candidates
POST /internal/kds/stations/{station_id}/tasks
GET /kds/stations/{station_id}/tasks
idempotency by idempotency_key
KdsTaskDisplayed Mongo event
tests
README updates
```

Use local KDS status:

```text
displayed
```

Do not implement:

```text
claim
complete
fail
busy_slots change
Fulfillment callbacks
Redis consumer
Kitchen Scheduler Worker
retry
DLQ
Prometheus metrics
```

Repeated delivery with the same idempotency_key must return the existing KDS task and must not create a duplicate.
