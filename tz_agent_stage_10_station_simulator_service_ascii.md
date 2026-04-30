# Agent Task Spec: Stage 10 - Station Simulator Service

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

Stage 9:
  kitchen-service implements KDS claim and complete
  claim protects capacity and double claim
  complete releases busy slot
```

This stage creates:

```text
services/station-simulator-service
```

The simulator is a demo service.
It imitates real station workers.

It only talks to Kitchen Service KDS API:

```http
GET /kds/stations/{station_id}/tasks
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
```

Important:

```text
Station Simulator Service must not talk directly to Fulfillment Service.
Station Simulator Service must not read or write any database.
Station Simulator Service must not read Redis Streams.
Station Simulator Service must not implement business status transitions.
```

---

## 1. Goal

Implement Station Simulator Service.

At the end of this stage:

```text
1. The simulator starts virtual station workers from config.
2. Each virtual worker polls its station KDS tasks.
3. Each virtual worker selects displayed tasks.
4. Each virtual worker calls KDS claim.
5. If claim succeeds, the virtual worker sleeps for simulated cooking duration.
6. The virtual worker calls KDS complete.
7. Metrics are exposed.
8. Logs are structured and include worker_id, station_id, task_id.
9. After an order is created and dispatched, simulator can move tasks through claim and complete.
10. Full flow can reach ready_for_pickup when all tasks are completed.
```

---

## 2. Scope

Implement:

```text
1. Python FastAPI or long-running Python service.
2. Service layout in services/station-simulator-service.
3. Config/env loading.
4. dk-common integration:
   - settings
   - logging
   - correlation id generation
   - health helper
5. KDS HTTP client.
6. Virtual worker configuration parser.
7. Polling loop per virtual worker.
8. Claim logic.
9. Simulated cooking sleep.
10. Complete logic.
11. Graceful startup and shutdown.
12. Prometheus metrics simulator_*.
13. Tests for config parser, worker loop, client calls, duration calculation.
14. README.
15. Dockerfile.
```

Recommended language:

```text
Python 3.11+
```

The original system allows Python or Go for this service.
Use Python for consistency with dk-common and FastAPI services.

---

## 3. Out of scope

Do not implement in this stage:

```text
- Kitchen Service KDS endpoints
- Fulfillment Service endpoints
- Kitchen Scheduler Worker logic
- Redis consumer
- Redis producer
- direct PostgreSQL access
- direct MongoDB access
- order creation
- menu creation
- recipe creation
- dispatch algorithm
- station selection algorithm
- retry/backoff/DLQ for Redis
- Kubernetes manifests unless already required by repo style
```

Do not add business logic for orders.

Do not call Fulfillment Service directly.

Do not change Kitchen Service database schema.

---

## 4. Expected directory layout

Create:

```text
services/
  station-simulator-service/
    pyproject.toml
    README.md
    Dockerfile
    app/
      __init__.py
      main.py
      core/
        __init__.py
        config.py
      kds_client/
        __init__.py
        client.py
        schemas.py
      simulator/
        __init__.py
        worker.py
        runner.py
        duration.py
        config_parser.py
      metrics/
        __init__.py
        metrics.py
    tests/
      conftest.py
      test_health.py
      test_config_parser.py
      test_duration.py
      test_kds_client.py
      test_worker_loop.py
```

It is acceptable to simplify slightly, but do not put all logic into app/main.py.

Recommended flow:

```text
main -> runner -> virtual worker -> kds client
```

---

## 5. Dependencies and dk-common integration

### 5.1. pyproject.toml

Create services/station-simulator-service/pyproject.toml:

```toml
[tool.poetry]
name = "station-simulator-service"
version = "0.1.0"
description = "Station Simulator Service for dark kitchen demo"
authors = ["Dark Kitchen Team"]
packages = [{ include = "app" }]

[tool.poetry.dependencies]
python = "^3.11"

dk-common = { path = "../../libs/python/dk-common", develop = true }

fastapi = "^0.115.0"
uvicorn = { extras = ["standard"], version = "^0.30.0" }

httpx = "^0.27.0"
pydantic = "^2.0.0"
pydantic-settings = "^2.0.0"
prometheus-client = "^0.20.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
respx = "^0.21.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

No SQLAlchemy.
No Alembic.
No asyncpg.
No redis.
No motor.

### 5.2. dk-common dependency rule

Station Simulator Service must use dk-common as a normal path dependency:

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

If dk-common has metrics helpers, they may be used.
If not, use prometheus-client directly inside station-simulator-service.

Do not put simulator-specific logic into dk-common.

---

## 6. Settings

Create app/core/config.py.

Use BaseServiceSettings from dk-common:

```python
from functools import lru_cache

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "station-simulator-service"

    kitchen_service_url: str = "http://localhost:8001"
    http_timeout_seconds: float = 3.0

    simulator_enabled: bool = True
    simulator_speed_factor: float = 60.0
    simulator_poll_interval_ms: int = 1000
    simulator_workers_config: str = "grill_1:2,fryer_1:1,packaging_1:1"

    simulator_min_duration_factor: float = 0.7
    simulator_max_duration_factor: float = 1.4

    prometheus_port: int = 9100


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Environment variables:

```env
SERVICE_NAME=station-simulator-service
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=readable

KITCHEN_SERVICE_URL=http://localhost:8001
HTTP_TIMEOUT_SECONDS=3

SIMULATOR_ENABLED=true
SIMULATOR_SPEED_FACTOR=60
SIMULATOR_POLL_INTERVAL_MS=1000
SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1,packaging_1:1
SIMULATOR_MIN_DURATION_FACTOR=0.7
SIMULATOR_MAX_DURATION_FACTOR=1.4

PROMETHEUS_PORT=9100
```

Docker env example:

```env
KITCHEN_SERVICE_URL=http://kitchen-service:8000
LOG_FORMAT=json
SIMULATOR_ENABLED=true
SIMULATOR_SPEED_FACTOR=60
SIMULATOR_POLL_INTERVAL_MS=1000
SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1,packaging_1:1
PROMETHEUS_PORT=9100
```

Validation:

```text
KITCHEN_SERVICE_URL must not be empty.
SIMULATOR_SPEED_FACTOR must be > 0.
SIMULATOR_POLL_INTERVAL_MS must be > 0.
SIMULATOR_MIN_DURATION_FACTOR must be > 0.
SIMULATOR_MAX_DURATION_FACTOR must be >= SIMULATOR_MIN_DURATION_FACTOR.
PROMETHEUS_PORT must be > 0.
```

---

## 7. Virtual worker configuration

Config format:

```text
SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1,packaging_1:1
```

Meaning:

```text
grill_1:2
  create two virtual workers for station_id grill_1

fryer_1:1
  create one virtual worker for station_id fryer_1

packaging_1:1
  create one virtual worker for station_id packaging_1
```

Generated worker IDs:

```text
grill_1-worker-1
grill_1-worker-2
fryer_1-worker-1
packaging_1-worker-1
```

If station IDs are UUIDs, generated worker IDs should still be stable:

```text
{station_id}-worker-{index}
```

Parser rules:

```text
1. Split by comma.
2. Each item must be station_id:count.
3. station_id must be non-empty.
4. count must be integer > 0.
5. Duplicate station_id entries should be rejected.
```

---

## 8. KDS HTTP client

Create:

```text
app/kds_client/client.py
app/kds_client/schemas.py
```

Use httpx.AsyncClient.

Base URL:

```text
KITCHEN_SERVICE_URL
```

Required methods:

```python
async def get_station_tasks(station_id: str) -> list[KdsTask]:
    ...

async def claim_task(station_id: str, task_id: str, worker_id: str) -> ClaimResponse:
    ...

async def complete_task(station_id: str, task_id: str, worker_id: str) -> CompleteResponse:
    ...
```

### 8.1. GET /kds/stations/{station_id}/tasks

Call:

```http
GET /kds/stations/{station_id}/tasks
```

Expected response:

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

### 8.2. POST /kds/stations/{station_id}/tasks/{task_id}/claim

Request:

```json
{
  "station_worker_id": "grill_1-worker-1"
}
```

Expected success:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "claimed",
  "claimed_by": "grill_1-worker-1",
  "claimed_at": "2026-04-30T10:02:00Z"
}
```

Expected conflicts:

```text
409 task_already_claimed
409 station_capacity_exceeded
```

Simulator behavior:

```text
If claim returns 409:
  log and skip task.
  do not sleep.
  continue polling later.
```

### 8.3. POST /kds/stations/{station_id}/tasks/{task_id}/complete

Request:

```json
{
  "station_worker_id": "grill_1-worker-1"
}
```

Expected success:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "completed",
  "claimed_by": "grill_1-worker-1",
  "completed_at": "2026-04-30T10:08:00Z"
}
```

If complete returns 503 or timeout:

```text
Log error.
Retry complete for the same task after a short delay if feasible.
Do not forget the task immediately.
```

MVP acceptable behavior:

```text
Try complete up to 3 times with small delay.
If still failing, log error and continue.
```

### 8.4. Correlation headers

Generate a correlation id per worker action cycle or per task.

Propagate:

```http
X-Correlation-ID
X-Request-ID
```

If dk-common provides helpers for correlation id, use them.
Otherwise generate UUID strings inside simulator.

---

## 9. Simulation algorithm

Implement in:

```text
app/simulator/worker.py
```

Each virtual worker runs a loop:

```text
1. Poll GET /kds/stations/{station_id}/tasks.
2. Filter tasks where status = displayed.
3. Pick one task.
4. Call claim.
5. If claim returns 200:
   - record claim success metric.
   - calculate simulated duration.
   - sleep simulated duration.
   - call complete.
   - record complete metric.
6. If claim returns 409:
   - record claim conflict metric.
   - continue loop.
7. If no displayed tasks:
   - sleep poll interval.
8. Repeat until shutdown.
```

Task selection rule:

```text
Pick earliest displayed task.
```

Use ordering from KDS response if it is already displayed_at ASC.
Otherwise sort locally by displayed_at.

Do not claim more than one task per virtual worker at the same time.
Each virtual worker is single-task-at-a-time.

---

## 10. Simulated cooking duration

Implement in:

```text
app/simulator/duration.py
```

Formula:

```text
actual_duration = estimated_duration_seconds * random(min_factor, max_factor) / speed_factor
```

Default values:

```text
min_factor = 0.7
max_factor = 1.4
speed_factor = 60
```

Example:

```text
estimated_duration_seconds = 480
random factor = 1.0
speed_factor = 60
actual sleep = 8 seconds
```

Rules:

```text
estimated_duration_seconds must be > 0.
speed_factor must be > 0.
min_factor and max_factor must be > 0.
max_factor must be >= min_factor.
duration should never be negative.
```

Testing:

```text
Use seeded random or inject random provider to make tests deterministic.
```

Important:

```text
Sleep is allowed in Station Simulator Service because it imitates human work.
Sleep is not allowed in Kitchen Scheduler Worker for cooking simulation.
```

---

## 11. Service lifecycle

Implement an async runner.

Recommended behavior:

```text
1. On startup, parse workers config.
2. If SIMULATOR_ENABLED=false:
   - start API server and health endpoint
   - do not start worker loops
3. If enabled:
   - start one asyncio task per virtual worker
4. On shutdown:
   - cancel worker tasks
   - close httpx client
   - stop cleanly
```

FastAPI lifespan is recommended.

The service should expose:

```http
GET /health
GET /metrics
```

No business API endpoints are required.

Optional debug endpoint:

```http
GET /simulator/workers
```

If implemented, it should return configured workers and basic state.
This endpoint is optional and must not mutate anything.

---

## 12. Metrics

Use prometheus-client.

Expose metrics on:

```http
GET /metrics
```

Required metrics:

```text
simulator_claim_attempts_total{station_id, worker_id}
simulator_claim_success_total{station_id, worker_id}
simulator_claim_conflicts_total{station_id, worker_id, reason}
simulator_completed_tasks_total{station_id, worker_id}
simulator_task_duration_seconds{station_id, worker_id}
simulator_poll_errors_total{station_id, worker_id, reason}
simulator_active_workers
```

Metric type recommendations:

```text
simulator_claim_attempts_total -> Counter
simulator_claim_success_total -> Counter
simulator_claim_conflicts_total -> Counter
simulator_completed_tasks_total -> Counter
simulator_task_duration_seconds -> Histogram
simulator_poll_errors_total -> Counter
simulator_active_workers -> Gauge
```

Avoid high-cardinality labels:

```text
Do not use task_id as metric label.
Do not use order_id as metric label.
Do not use correlation_id as metric label.
```

Allowed labels for this MVP:

```text
station_id
worker_id
reason
```

---

## 13. Logging

Use dk-common logging.

Structured logs should include:

```text
timestamp
level
service
environment
message
correlation_id
worker_id
station_id
task_id
kds_task_id
order_id
operation
error
```

Important log events:

```text
simulator_started
worker_started
poll_started
displayed_task_found
claim_attempt
claim_success
claim_conflict
simulated_cooking_started
simulated_cooking_completed
complete_attempt
complete_success
complete_failed
worker_stopped
simulator_stopped
```

Do not log huge response payloads at info level.
Use debug if necessary.

---

## 14. Error handling

### 14.1. Poll errors

If GET tasks fails:

```text
1. Log error.
2. Increment simulator_poll_errors_total.
3. Sleep poll interval.
4. Continue loop.
```

### 14.2. Claim conflicts

If claim returns 409:

```text
1. Log conflict.
2. Increment simulator_claim_conflicts_total.
3. Do not sleep cooking duration.
4. Continue loop.
```

Common reasons:

```text
task_already_claimed
station_capacity_exceeded
task_not_displayed
```

### 14.3. Claim temporary failures

If claim returns 5xx or timeout:

```text
1. Log error.
2. Sleep poll interval.
3. Continue loop.
```

Do not crash the worker loop.

### 14.4. Complete temporary failures

If complete returns 5xx or timeout:

```text
1. Retry complete up to 3 times.
2. Use small delay, for example poll interval.
3. If still failing, log error.
4. Continue loop.
```

Note:

```text
If complete fails permanently, the task may remain claimed in Kitchen Service.
This is acceptable for MVP diagnostics.
```

### 14.5. Worker loop safety

Each worker loop must catch unexpected exceptions.

Behavior:

```text
Log exception.
Sleep poll interval.
Continue.
```

The whole service should not crash because one task failed.

---

## 15. Optional worker state

It is useful to track in memory:

```text
worker_id
station_id
status
current_task_id
last_error
last_poll_at
completed_tasks_count
```

This is optional.

If implemented, expose:

```http
GET /simulator/workers
```

Example response:

```json
[
  {
    "worker_id": "grill_1-worker-1",
    "station_id": "grill_1",
    "status": "idle",
    "current_task_id": null,
    "completed_tasks_count": 3,
    "last_error": null
  }
]
```

Do not persist worker state in DB.

---

## 16. Dockerfile

Create services/station-simulator-service/Dockerfile.

Example:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /repo

RUN pip install --no-cache-dir uv

COPY libs/python/dk-common /repo/libs/python/dk-common
COPY services/station-simulator-service /repo/services/station-simulator-service

RUN uv pip install --system /repo/libs/python/dk-common
RUN uv pip install --system /repo/services/station-simulator-service

WORKDIR /repo/services/station-simulator-service

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Recommended MVP:

```text
Serve /health and /metrics from FastAPI on port 8000.
```

---

## 17. Docker Compose notes

If compose exists, add service:

```yaml
services:
  station-simulator-service:
    build:
      context: ../..
      dockerfile: services/station-simulator-service/Dockerfile
    environment:
      SERVICE_NAME: station-simulator-service
      ENVIRONMENT: local
      LOG_FORMAT: json
      KITCHEN_SERVICE_URL: http://kitchen-service:8000
      SIMULATOR_ENABLED: "true"
      SIMULATOR_SPEED_FACTOR: "60"
      SIMULATOR_POLL_INTERVAL_MS: "1000"
      SIMULATOR_WORKERS_CONFIG: "grill_1:2,fryer_1:1,packaging_1:1"
    depends_on:
      - kitchen-service
    profiles:
      - demo
```

Reason:

```text
Simulator is a demo service.
It should be easy to run MVP without it.
```

---

## 18. Tests

### 18.1. Test command

Tests must run from services/station-simulator-service:

```bash
poetry run pytest
```

### 18.2. Required tests

#### test_health.py

Check:

```text
GET /health returns 200
response.status = ok
response.service = station-simulator-service
```

#### test_config_parser.py

Check:

```text
grill_1:2 creates two workers
multiple stations are parsed
empty config raises validation error
invalid item raises validation error
count <= 0 raises validation error
duplicate station_id raises validation error
generated worker ids are stable
```

#### test_duration.py

Check:

```text
duration uses estimated_duration_seconds / speed_factor
duration applies min_factor and max_factor
duration is positive
invalid speed_factor raises error
invalid factor range raises error
deterministic random provider makes test stable
```

#### test_kds_client.py

Use respx or httpx MockTransport.

Check:

```text
get_station_tasks calls GET /kds/stations/{station_id}/tasks
claim_task sends station_worker_id
complete_task sends station_worker_id
correlation headers are included
409 claim conflict is represented as a typed result or exception
5xx is represented as retryable error
```

#### test_worker_loop.py

Use fake KDS client and fake sleep function.

Check:

```text
worker polls tasks
worker ignores non-displayed tasks
worker claims displayed task
worker sleeps after successful claim
worker completes after sleep
worker does not sleep if claim returns conflict
worker continues after poll error
worker retries complete on temporary failure
```

Important:

```text
Tests must not actually sleep for real cooking duration.
Inject sleep function or use monkeypatch.
```

#### test_metrics.py

Check:

```text
claim attempts counter increments
claim success counter increments
claim conflict counter increments
completed tasks counter increments
task duration histogram observes duration
```

---

## 19. Integration or manual test scenario

Add to README.

Prerequisites:

```text
1. Start postgres, redis, mongo.
2. Start kitchen-service.
3. Start menu-service.
4. Start fulfillment-service.
5. Start kitchen-scheduler-worker.
6. Run migrations.
7. Create kitchen and stations.
8. Create menu item and recipe.
9. Create availability.
10. Start station-simulator-service.
11. Create order.
```

Expected flow:

```text
1. Fulfillment creates tasks and publishes Redis messages.
2. Go worker dispatches tasks to KDS.
3. Simulator polls KDS station tasks.
4. Simulator claims displayed task.
5. Kitchen Service calls Fulfillment /start.
6. Simulator sleeps simulated duration.
7. Simulator completes task.
8. Kitchen Service calls Fulfillment /complete.
9. Fulfillment marks task done.
10. When all tasks are done, order.status becomes ready_for_pickup.
```

Manual checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
curl http://localhost:8001/kds/stations/{station_id}/tasks
curl http://localhost:8003/orders/{order_id}
curl http://localhost:8003/orders/{order_id}/tasks
```

Expected:

```text
station tasks become completed
fulfillment tasks become done
order becomes ready_for_pickup
simulator metrics increase
```

---

## 20. README

Create services/station-simulator-service/README.md.

README must include:

```text
1. Service purpose.
2. Stage boundary.
3. Dependency installation.
4. Environment variables.
5. Worker config format.
6. Speed factor explanation.
7. Local run.
8. Docker run.
9. Metrics.
10. Manual demo scenario.
11. Troubleshooting.
```

Local run example:

```bash
cd services/station-simulator-service

poetry install
poetry run uvicorn app.main:app --reload
poetry run pytest
```

Example env:

```bash
export KITCHEN_SERVICE_URL=http://localhost:8001
export SIMULATOR_ENABLED=true
export SIMULATOR_SPEED_FACTOR=60
export SIMULATOR_POLL_INTERVAL_MS=1000
export SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1,packaging_1:1
```

---

## 21. Troubleshooting notes

Add to README.

### 21.1. Simulator sees no tasks

Check:

```text
Kitchen Scheduler Worker is running.
Task is displayed in KDS.
Station id in SIMULATOR_WORKERS_CONFIG matches actual station_id.
GET /kds/stations/{station_id}/tasks returns displayed tasks.
```

### 21.2. Claims return station_capacity_exceeded

Check:

```text
station.capacity
station.busy_slots
number of virtual workers for same station
tasks stuck in claimed status
```

### 21.3. Complete fails

Check:

```text
Fulfillment Service is running.
Fulfillment /internal/tasks/{task_id}/complete works.
KDS task is claimed by the same station_worker_id.
```

### 21.4. Order does not reach ready_for_pickup

Check:

```text
All recipe steps were dispatched.
All station types have simulator workers configured.
Packaging tasks may be waiting for grill dependencies.
Go worker is running and retrying not-ready tasks.
```

---

## 22. Definition of Done

Stage is complete when:

```text
1. services/station-simulator-service exists.
2. Service starts with uvicorn.
3. dk-common is connected through Poetry path dependency.
4. No sys.path hacks.
5. No relative imports from libs.
6. /health works.
7. /metrics works.
8. SIMULATOR_WORKERS_CONFIG is parsed.
9. Virtual workers are created from config.
10. Each virtual worker polls GET /kds/stations/{station_id}/tasks.
11. Worker filters displayed tasks.
12. Worker calls claim for displayed tasks.
13. Worker handles claim 409 conflicts without crashing.
14. Worker sleeps simulated duration after successful claim.
15. Worker calls complete after simulated duration.
16. Worker retries complete on temporary failure.
17. Metrics simulator_claim_attempts_total are exposed.
18. Metrics simulator_claim_success_total are exposed.
19. Metrics simulator_claim_conflicts_total are exposed.
20. Metrics simulator_completed_tasks_total are exposed.
21. Metrics simulator_task_duration_seconds are exposed.
22. Structured logs include worker_id, station_id, task_id.
23. Tests pass.
24. Simulator does not call Fulfillment Service directly.
25. Simulator does not read Redis.
26. Simulator does not access PostgreSQL.
27. Simulator does not implement dispatch logic.
28. README documents local and demo usage.
```

---

## 23. Short instruction for the agent

Implement Stage 10 in services/station-simulator-service.

Use Python 3.11, FastAPI, httpx, prometheus-client, and dk-common.

Implement:

```text
KDS client
worker config parser
virtual worker loop
poll displayed KDS tasks
claim
simulated cooking sleep
complete
metrics
structured logging
tests
Dockerfile
README
```

Use only Kitchen Service KDS API:

```http
GET /kds/stations/{station_id}/tasks
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
```

Use duration formula:

```text
actual_duration = estimated_duration_seconds * random(0.7, 1.4) / SIMULATOR_SPEED_FACTOR
```

Do not implement:

```text
Fulfillment direct client
Redis client
database access
dispatch algorithm
station selection
Go worker logic
order creation
```
