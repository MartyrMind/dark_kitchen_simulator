# Agent Task Spec: Stage 8 - Kitchen Scheduler Worker in Go

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
```

This stage creates:

```text
services/kitchen-scheduler-worker
```

The worker is written in Go.

The worker role is:

```text
Redis Streams -> choose station_id -> deliver to KDS -> mark displayed -> XACK
```

Important:

```text
The worker is not a cook.
The worker does not execute kitchen tasks.
The worker does not sleep for estimated_duration_seconds.
The worker does not set tasks to in_progress.
The worker does not set tasks to done.
```

---

## 1. Goal

Implement Kitchen Scheduler Worker in Go.

At the end of this stage:

```text
1. Worker reads Redis Streams through consumer groups.
2. Worker checks task snapshot through Fulfillment Service.
3. Worker checks dispatch-readiness through Fulfillment Service.
4. Worker asks Kitchen Service for dispatch candidates.
5. Worker chooses a concrete station_id.
6. Worker delivers task to KDS.
7. Worker calls Fulfillment mark-displayed.
8. Worker XACKs Redis message only after successful KDS delivery and successful mark-displayed.
9. Worker supports retry/backoff.
10. Worker sends messages to DLQ after max attempts.
11. Worker exposes Prometheus metrics.
12. Worker writes structured logs.
```

---

## 2. Scope

Implement:

```text
1. Go module in services/kitchen-scheduler-worker.
2. Config/env loading.
3. Structured logging via slog or zerolog.
4. Redis Streams consumer group.
5. XREADGROUP loop.
6. Fulfillment HTTP client.
7. Kitchen/KDS HTTP client.
8. Dispatch algorithm.
9. Station selection algorithm.
10. Idempotent KDS delivery.
11. Idempotent mark-displayed handling.
12. Retry/backoff.
13. DLQ publishing.
14. Prometheus metrics endpoint.
15. Unit tests for pure logic.
16. HTTP client tests with httptest.
17. Redis integration tests if feasible.
18. README.
19. Dockerfile.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- KDS claim endpoint
- KDS complete endpoint
- station busy_slots changes
- Station Simulator
- Fulfillment task start endpoint implementation
- Fulfillment task complete endpoint implementation
- creating orders
- creating kitchen tasks
- writing to PostgreSQL directly
- direct SQL access to any service database
- Kubernetes manifests unless already required by repo style
- full Grafana dashboards
```

Important:

```text
The worker must use HTTP APIs only.
The worker must not connect to PostgreSQL.
The worker must not mutate kitchen_tasks directly.
The worker must not mutate kds_station_tasks directly.
```

---

## 4. Expected directory layout

Create:

```text
services/
  kitchen-scheduler-worker/
    go.mod
    go.sum
    Dockerfile
    README.md
    cmd/
      worker/
        main.go
    internal/
      config/
        config.go
      logging/
        logging.go
      redisstream/
        consumer.go
        message.go
        retry.go
        dlq.go
      fulfillment/
        client.go
        types.go
      kitchen/
        client.go
        types.go
      scheduler/
        dispatcher.go
        station_selector.go
        idempotency.go
      metrics/
        metrics.go
      clock/
        clock.go
```

Tests can live next to packages:

```text
internal/scheduler/dispatcher_test.go
internal/scheduler/station_selector_test.go
internal/redisstream/message_test.go
internal/fulfillment/client_test.go
internal/kitchen/client_test.go
```

It is acceptable to simplify the layout, but do not put all logic into main.go.

---

## 5. Go dependencies

Use Go 1.22 or newer.

Recommended go.mod:

```go
module github.com/your-org/dark-kitchen/services/kitchen-scheduler-worker

go 1.22
```

Recommended dependencies:

```text
github.com/redis/go-redis/v9
github.com/prometheus/client_golang/prometheus
github.com/prometheus/client_golang/prometheus/promhttp
```

For logging, use one of:

```text
log/slog from standard library
github.com/rs/zerolog
```

Preferred for MVP:

```text
log/slog
```

For HTTP clients:

```text
net/http from standard library
```

Optional:

```text
github.com/go-resty/resty/v2
```

Preferred for MVP:

```text
net/http
```

---

## 6. Configuration

Create internal/config/config.go.

Environment variables:

```env
WORKER_ID=scheduler-worker-1
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=json

REDIS_URL=redis://localhost:6379/0
REDIS_STREAM_PATTERNS=stream:kitchen:*:station:*
REDIS_CONSUMER_GROUP=group:kitchen-scheduler-workers

FULFILLMENT_SERVICE_URL=http://localhost:8003
KITCHEN_SERVICE_URL=http://localhost:8001

STREAM_SCAN_INTERVAL_MS=500
XREAD_BLOCK_MS=5000
XREAD_COUNT=10

MAX_DISPATCH_ATTEMPTS=5
DISPATCH_BACKOFF_BASE_MS=1000
DISPATCH_BACKOFF_MAX_MS=30000

HTTP_TIMEOUT_MS=3000
PROMETHEUS_PORT=9090
```

Required config fields:

```text
worker_id
environment
log_level
log_format
redis_url
redis_stream_patterns
redis_consumer_group
fulfillment_service_url
kitchen_service_url
stream_scan_interval
xread_block
xread_count
max_dispatch_attempts
dispatch_backoff_base
dispatch_backoff_max
http_timeout
prometheus_port
```

Validation:

```text
WORKER_ID must not be empty.
REDIS_URL must not be empty.
FULFILLMENT_SERVICE_URL must not be empty.
KITCHEN_SERVICE_URL must not be empty.
MAX_DISPATCH_ATTEMPTS must be > 0.
HTTP_TIMEOUT_MS must be > 0.
```

---

## 7. Redis Streams

### 7.1. Stream names

Fulfillment Service publishes tasks to streams:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

Examples:

```text
stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:grill
stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:packaging
```

Worker must discover or configure streams.

MVP approach:

```text
Periodically scan Redis keys matching REDIS_STREAM_PATTERNS.
For each stream, ensure consumer group exists.
Read from all discovered streams.
```

Alternative acceptable MVP approach:

```text
Use explicitly configured stream list from REDIS_STREAMS.
```

If using scan pattern, implement:

```text
SCAN stream:kitchen:*:station:*
```

Do not scan DLQ streams:

```text
stream:kitchen:*:station:*:dlq
```

### 7.2. Consumer group

Consumer group name:

```text
group:kitchen-scheduler-workers
```

Consumer name:

```text
WORKER_ID
```

For each stream, create consumer group if it does not exist:

```text
XGROUP CREATE {stream} {group} 0 MKSTREAM
```

If group already exists, ignore BUSYGROUP error.

### 7.3. XREADGROUP

Use XREADGROUP to read new messages:

```text
XREADGROUP GROUP {group} {consumer} COUNT {count} BLOCK {block_ms} STREAMS {stream} >
```

MVP can read stream by stream or multiple streams at once.

Required behavior:

```text
1. Read message.
2. Parse message payload.
3. Dispatch message.
4. XACK only after successful KDS delivery and successful mark-displayed.
```

### 7.4. Redis message payload

Expected fields:

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

Recommended fields:

```text
correlation_id
recipe_step_order
item_unit_index
```

Parsing rules:

```text
task_id required
order_id required
kitchen_id required
station_type required
operation required
menu_item_id required
estimated_duration_seconds required int > 0
attempt optional, default 1
pickup_deadline optional
menu_item_name optional
```

Invalid message behavior:

```text
If required fields are missing or invalid:
  send to DLQ with reason invalid_message
  XACK original message
```

---

## 8. HTTP APIs used by worker

### 8.1. Fulfillment Service

Base URL:

```text
FULFILLMENT_SERVICE_URL
```

Required calls:

```http
GET /internal/tasks/{task_id}
GET /internal/tasks/{task_id}/dispatch-readiness
POST /internal/tasks/{task_id}/mark-displayed
POST /internal/tasks/{task_id}/dispatch-failed
```

Optional call:

```http
POST /internal/tasks/{task_id}/retry
```

#### GET /internal/tasks/{task_id}

Expected response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "menu_item_id": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce",
  "station_type": "grill",
  "operation": "cook_patty",
  "status": "queued",
  "estimated_duration_seconds": 480,
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "attempts": 1
}
```

Dispatchable statuses:

```text
queued
retrying
```

If task status is one of:

```text
displayed
in_progress
done
cancelled
failed
```

Then:

```text
XACK message
skip dispatch
```

Reason:

```text
Redis message is stale.
Fulfillment is source of truth.
```

#### GET /internal/tasks/{task_id}/dispatch-readiness

Expected ready response:

```json
{
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "ready_to_dispatch": true,
  "waiting_for": []
}
```

Expected not ready response:

```json
{
  "task_id": "de0c8a5f-233e-4f2c-9b7f-e35942574d9f",
  "ready_to_dispatch": false,
  "waiting_for": [
    "8f39f9fc-9c17-4995-8767-fd7e62c44852"
  ]
}
```

If not ready:

```text
schedule delayed retry
XACK original message
do not deliver to KDS
```

#### POST /internal/tasks/{task_id}/mark-displayed

Request:

```json
{
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "displayed_at": "2026-04-30T10:00:01Z",
  "dispatcher_id": "scheduler-worker-1"
}
```

If mark-displayed succeeds:

```text
XACK Redis message
```

If Fulfillment says task already displayed and station/kds match:

```text
XACK Redis message
```

If Fulfillment returns temporary error:

```text
retry mark-displayed or schedule retry
do not XACK until success unless delayed retry re-enqueues safely
```

MVP acceptable behavior:

```text
If KDS delivery succeeds but mark-displayed fails temporarily:
  keep retrying mark-displayed a few times in-process.
  If still fails, schedule retry message and XACK original.
```

The retry path must be idempotent because KDS delivery uses idempotency_key.

#### POST /internal/tasks/{task_id}/dispatch-failed

Request:

```json
{
  "reason": "no_dispatch_candidates",
  "failed_at": "2026-04-30T10:05:00Z",
  "dispatcher_id": "scheduler-worker-1",
  "attempts": 5
}
```

Call this after moving message to DLQ.

### 8.2. Kitchen Service / KDS

Base URL:

```text
KITCHEN_SERVICE_URL
```

Required calls:

```http
GET /internal/kds/dispatch-candidates?kitchen_id={kitchen_id}&station_type={station_type}
POST /internal/kds/stations/{station_id}/tasks
```

#### GET /internal/kds/dispatch-candidates

Expected response:

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

Worker filters candidates:

```text
status = available
health = ok
visible_backlog_size < visible_backlog_limit
```

#### POST /internal/kds/stations/{station_id}/tasks

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

Expected response:

```json
{
  "kds_task_id": "9be0ec11-1be0-43dd-baf3-44cbf3043a9c",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "station_id": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
  "status": "displayed"
}
```

Idempotency key:

```text
{task_id}:dispatch:v1
```

Repeated delivery with the same idempotency_key must be safe.

---

## 9. Dispatch algorithm

Implement in internal/scheduler/dispatcher.go.

Algorithm:

```text
1. Read Redis Stream message through XREADGROUP.
2. Parse Redis task message.
3. Get task snapshot from Fulfillment Service.
4. If task status is displayed, in_progress, done, cancelled, or failed:
   - XACK message
   - record skipped metric
   - stop processing
5. If task status is not queued or retrying:
   - schedule retry or XACK according to reason
   - stop processing
6. Get dispatch-readiness from Fulfillment Service.
7. If ready_to_dispatch = false:
   - schedule delayed retry
   - XACK original message
   - stop processing
8. Get dispatch candidates from Kitchen Service.
9. Filter candidates:
   - status = available
   - health = ok
   - visible_backlog_size < visible_backlog_limit
10. If no candidates:
   - schedule delayed retry
   - XACK original message
   - stop processing
11. Select station_id.
12. Deliver task to KDS using POST /internal/kds/stations/{station_id}/tasks.
13. If KDS delivery succeeds or returns existing idempotent task:
   - call Fulfillment mark-displayed.
14. If mark-displayed succeeds or is idempotently already displayed:
   - XACK Redis message
   - record success metrics
15. If any temporary error happens:
   - retry with backoff
   - if attempts exhausted, move to DLQ and call dispatch-failed
```

Important:

```text
XACK only after both:
  KDS delivery is successful
  Fulfillment mark-displayed is successful or idempotently already displayed
```

---

## 10. Station selection algorithm

Implement in internal/scheduler/station_selector.go.

MVP algorithm:

```text
1. Filter candidates where:
   - status = available
   - health = ok
   - visible_backlog_size < visible_backlog_limit

2. Sort by:
   - visible_backlog_size ASC
   - busy_slots ASC

3. Pick first candidate.
```

Tie-breaking:

```text
If visible_backlog_size and busy_slots are equal,
pick station with lexicographically smallest station_id for deterministic tests.
```

Extended score optional:

```text
score = visible_backlog_size * 10 + busy_slots * 20
```

Do not use station capacity directly for dispatch.
Capacity is enforced during claim in later stage.

---

## 11. Retry and backoff

### 11.1. Attempt count

Use attempt from Redis message if present.

If missing:

```text
attempt = 1
```

When scheduling retry:

```text
next_attempt = attempt + 1
```

If next_attempt > MAX_DISPATCH_ATTEMPTS:

```text
move to DLQ
call Fulfillment dispatch-failed
XACK original
```

### 11.2. Backoff

Use exponential backoff with cap:

```text
delay = min(DISPATCH_BACKOFF_BASE_MS * 2^(attempt - 1), DISPATCH_BACKOFF_MAX_MS)
```

Add jitter if simple:

```text
delay = delay + random(0, delay * 0.2)
```

Jitter is optional for MVP.

### 11.3. Delayed retry implementation

Redis Streams do not provide native delayed messages.

Acceptable MVP approach:

```text
Use a goroutine:
  sleep(backoff)
  XADD a new message to the same stream with attempt = next_attempt
  XACK original message
```

Better approach:

```text
Use Redis sorted set as delayed queue.
```

For Stage 8, goroutine sleep is acceptable for dispatch retry delay.

Important:

```text
Do not use sleep to simulate cooking.
Sleep is only acceptable for retry/backoff scheduling.
```

### 11.4. Retry reasons

Use stable reason strings:

```text
task_not_ready
no_dispatch_candidates
kitchen_service_unavailable
fulfillment_service_unavailable
kds_delivery_failed
mark_displayed_failed
invalid_message
unexpected_error
```

---

## 12. DLQ

DLQ stream format:

```text
stream:kitchen:{kitchen_id}:station:{station_type}:dlq
```

DLQ message should include original message fields plus:

```text
failure_reason
failed_at
worker_id
attempts
original_stream
original_message_id
```

Example:

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
  "attempt": "5",
  "failure_reason": "no_dispatch_candidates",
  "failed_at": "2026-04-30T10:05:00Z",
  "worker_id": "scheduler-worker-1",
  "original_stream": "stream:kitchen:d53b7d88-b23c-4bb8-a403-6238c810092a:station:grill",
  "original_message_id": "1714470000000-0"
}
```

After writing to DLQ:

```text
1. Call Fulfillment dispatch-failed.
2. XACK original message.
```

If dispatch-failed call fails:

```text
Log error.
Retry call a few times if simple.
Do not block forever.
For MVP, after DLQ write, XACK original to avoid infinite poison message loop.
```

---

## 13. Correlation ID

Redis messages may contain:

```text
correlation_id
```

Worker must propagate correlation id to HTTP calls:

```http
X-Correlation-ID: {correlation_id}
X-Request-ID: generated per outbound request
```

If Redis message has no correlation_id:

```text
Generate one per dispatch attempt.
```

Structured logs must include:

```text
correlation_id
request_id if available
task_id
order_id
kitchen_id
station_type
station_id if selected
worker_id
redis_stream
redis_message_id
```

---

## 14. Structured logging

Use slog or zerolog.

Recommended fields:

```text
timestamp
level
service
environment
message
worker_id
correlation_id
task_id
order_id
kitchen_id
station_type
station_id
redis_stream
redis_message_id
error
```

Service name:

```text
kitchen-scheduler-worker
```

JSON logs are required for Docker/Kubernetes.

Readable logs are optional for local development.

Do not log full payloads at info level if they may be large.
Debug logging can include payload details.

---

## 15. Metrics

Expose Prometheus metrics on:

```text
:{PROMETHEUS_PORT}/metrics
```

Recommended endpoint:

```text
GET /metrics
```

Use prometheus/client_golang.

Required metrics:

```text
dispatch_attempts_total{kitchen_id, station_type}
dispatch_success_total{kitchen_id, station_type, station_id}
dispatch_failed_total{kitchen_id, station_type, reason}
dispatch_retries_total{kitchen_id, station_type, reason}
dispatch_latency_seconds{kitchen_id, station_type}
redis_pending_messages{kitchen_id, station_type}
redis_dlq_messages_total{kitchen_id, station_type}
```

Simpler MVP metrics acceptable:

```text
dispatch_attempts_total
dispatch_success_total
dispatch_failed_total
dispatch_retries_total
dispatch_latency_seconds
redis_dlq_messages_total
```

Avoid high-cardinality labels:

```text
Do not use task_id as metric label.
Do not use order_id as metric label.
Do not use correlation_id as metric label.
Do not use redis_message_id as metric label.
```

Allowed labels:

```text
service
kitchen_id
station_type
station_id
reason
```

If kitchen_id and station_id cardinality becomes high in future, revisit.

---

## 16. Health endpoint

Expose a lightweight health endpoint if simple.

Recommended:

```text
GET /health
```

Can be served from the same HTTP server as metrics.

Response:

```json
{
  "status": "ok",
  "service": "kitchen-scheduler-worker",
  "worker_id": "scheduler-worker-1"
}
```

If implementing only /metrics in this stage, document it in README.
Preferred MVP: implement both /health and /metrics.

---

## 17. Error classification

Classify errors as permanent or retryable.

### 17.1. Permanent errors

Examples:

```text
invalid Redis message
task not found in Fulfillment
task cancelled
task failed
task already done
station_type mismatch that cannot be fixed by retry
KDS conflict due to same task_id with different idempotency_key
```

Behavior:

```text
XACK stale or already terminal tasks.
DLQ invalid messages if they cannot be safely skipped.
Call dispatch-failed if task exists and dispatch permanently failed.
```

### 17.2. Retryable errors

Examples:

```text
Fulfillment Service timeout
Kitchen Service timeout
Redis temporary failure
no dispatch candidates
task not ready because dependencies are not done
KDS delivery temporary 5xx
mark-displayed temporary 5xx
```

Behavior:

```text
schedule retry until MAX_DISPATCH_ATTEMPTS.
After max attempts, DLQ and dispatch-failed.
```

### 17.3. HTTP status handling

Suggested rules:

```text
2xx:
  success

400/422:
  permanent error unless explicitly idempotent

404 from Fulfillment snapshot:
  stale/invalid task, XACK or DLQ with task_not_found

404 from Kitchen station delivery:
  retry or DLQ depending on reason

409 from KDS delivery:
  if idempotent existing task is returned, treat success
  otherwise permanent conflict

409 from mark-displayed:
  if already displayed with matching station/kds, treat success
  otherwise permanent conflict

5xx:
  retryable
```

---

## 18. Idempotency

KDS delivery idempotency key:

```text
{task_id}:dispatch:v1
```

Required behavior:

```text
Repeated KDS delivery must not create duplicate KDS tasks.
Repeated mark-displayed must not corrupt Fulfillment task.
```

Worker behavior if processing the same Redis message twice:

```text
1. KDS delivery with same idempotency_key returns existing KDS task.
2. mark-displayed returns success or idempotent already displayed.
3. Worker XACKs message.
```

Worker behavior if multiple worker replicas race:

```text
KDS unique idempotency and Fulfillment transition validation protect correctness.
Only one dispatch should become authoritative.
Other attempts should end in idempotent success or conflict handling.
```

---

## 19. Concurrency model

MVP acceptable:

```text
Single process with configurable number of goroutines.
Each goroutine reads and processes messages.
```

Config option optional:

```env
WORKER_CONCURRENCY=4
```

If implemented:

```text
Limit concurrent dispatches to WORKER_CONCURRENCY.
```

Avoid unbounded goroutine creation.

For retry goroutines, protect from explosion:

```text
Do not create unbounded sleepers under high load.
MVP may be simple, but keep code structured for later delayed queue.
```

---

## 20. Dockerfile

Create services/kitchen-scheduler-worker/Dockerfile.

Example:

```dockerfile
FROM golang:1.22-alpine AS builder

WORKDIR /src

COPY services/kitchen-scheduler-worker/go.mod services/kitchen-scheduler-worker/go.sum ./
RUN go mod download

COPY services/kitchen-scheduler-worker ./

RUN CGO_ENABLED=0 GOOS=linux go build -o /out/kitchen-scheduler-worker ./cmd/worker

FROM alpine:3.20

WORKDIR /app

COPY --from=builder /out/kitchen-scheduler-worker /app/kitchen-scheduler-worker

EXPOSE 9090

CMD ["/app/kitchen-scheduler-worker"]
```

Build context should be repository root or service directory depending on compose style.

If build context is repo root:

```yaml
services:
  kitchen-scheduler-worker:
    build:
      context: ../..
      dockerfile: services/kitchen-scheduler-worker/Dockerfile
```

---

## 21. Docker Compose notes

If compose exists, add:

```yaml
services:
  kitchen-scheduler-worker:
    build:
      context: ../..
      dockerfile: services/kitchen-scheduler-worker/Dockerfile
    environment:
      WORKER_ID: scheduler-worker-1
      ENVIRONMENT: local
      LOG_FORMAT: json
      REDIS_URL: redis://redis:6379/0
      REDIS_STREAM_PATTERNS: stream:kitchen:*:station:*
      REDIS_CONSUMER_GROUP: group:kitchen-scheduler-workers
      FULFILLMENT_SERVICE_URL: http://fulfillment-service:8000
      KITCHEN_SERVICE_URL: http://kitchen-service:8000
      STREAM_SCAN_INTERVAL_MS: "500"
      MAX_DISPATCH_ATTEMPTS: "5"
      DISPATCH_BACKOFF_BASE_MS: "1000"
      DISPATCH_BACKOFF_MAX_MS: "30000"
      HTTP_TIMEOUT_MS: "3000"
      PROMETHEUS_PORT: "9090"
    depends_on:
      - redis
      - fulfillment-service
      - kitchen-service
```

Do not add station-simulator in this stage unless already present.

---

## 22. Unit tests

### 22.1. Test command

From worker directory:

```bash
cd services/kitchen-scheduler-worker
go test ./...
```

### 22.2. Required tests

#### config tests

Check:

```text
defaults are loaded
env overrides work
invalid MAX_DISPATCH_ATTEMPTS fails
missing required URLs fail
```

#### Redis message parsing tests

Check:

```text
valid message parses correctly
missing task_id returns error
missing kitchen_id returns error
invalid estimated_duration_seconds returns error
missing attempt defaults to 1
```

#### stream helper tests

Check:

```text
DLQ stream is stream:kitchen:{kitchen_id}:station:{station_type}:dlq
normal stream is not mistaken for DLQ
DLQ streams are ignored during scan filtering
```

#### station selector tests

Check:

```text
filters unavailable stations
filters stations with health != ok
filters visible_backlog_size >= visible_backlog_limit
chooses minimal visible_backlog_size
uses busy_slots as tie breaker
uses station_id as deterministic final tie breaker
```

#### dispatch algorithm tests with fake clients

Check:

```text
terminal task status causes XACK and no KDS call
not ready task schedules retry and XACKs original
no candidates schedules retry and XACKs original
successful flow calls KDS delivery then mark-displayed then XACK
KDS delivery failure schedules retry
mark-displayed failure schedules retry
max attempts writes DLQ and calls dispatch-failed
invalid message writes DLQ and XACKs original
```

#### idempotency tests

Check:

```text
idempotency_key is task_id:dispatch:v1
KDS already existing response is treated as success
mark-displayed already displayed response is treated as success if station/kds match
```

#### metrics tests

Check:

```text
dispatch_attempts_total increments
dispatch_success_total increments on success
dispatch_failed_total increments on failure
dispatch_retries_total increments on retry
```

---

## 23. Integration tests

Integration tests are optional but recommended.

### 23.1. Redis integration test

Using real Redis or test container:

```text
1. Create stream.
2. Create consumer group.
3. XADD message.
4. Worker reads message.
5. Fake HTTP servers return successful responses.
6. Worker XACKs message.
7. Pending count becomes 0.
```

### 23.2. HTTP client tests

Use httptest.

Fulfillment client tests:

```text
GetTaskSnapshot parses response.
GetDispatchReadiness parses response.
MarkDisplayed sends correct payload.
DispatchFailed sends correct payload.
Correlation headers are propagated.
```

Kitchen client tests:

```text
GetDispatchCandidates parses response.
DeliverTaskToKDS sends correct payload.
DeliverTaskToKDS parses kds_task_id.
Correlation headers are propagated.
```

---

## 24. Manual test scenario

Add to README.

Prerequisites:

```text
1. Start postgres, redis, mongo.
2. Start kitchen-service.
3. Start menu-service.
4. Start fulfillment-service.
5. Run migrations for Python services.
6. Create kitchen and stations.
7. Create menu item and recipe.
8. Create order.
9. Confirm tasks are queued and Redis streams contain messages.
10. Start kitchen-scheduler-worker.
```

Expected:

```text
1. Worker reads Redis Stream message.
2. Worker calls Fulfillment task snapshot.
3. Worker calls dispatch-readiness.
4. Worker calls Kitchen dispatch candidates.
5. Worker delivers task to KDS.
6. Worker calls Fulfillment mark-displayed.
7. Worker XACKs Redis message.
8. GET /kds/stations/{station_id}/tasks returns displayed task.
9. GET /orders/{order_id}/tasks shows task status displayed.
```

Example Redis checks:

```bash
redis-cli KEYS 'stream:kitchen:*'
redis-cli XPENDING stream:kitchen:{kitchen_id}:station:grill group:kitchen-scheduler-workers
redis-cli XRANGE stream:kitchen:{kitchen_id}:station:grill - +
```

Example service checks:

```bash
curl http://localhost:8001/kds/stations/{station_id}/tasks
curl http://localhost:8003/orders/{order_id}/tasks
curl http://localhost:9090/metrics
```

---

## 25. README

Create services/kitchen-scheduler-worker/README.md.

README must include:

```text
1. Worker purpose.
2. Stage boundary.
3. Environment variables.
4. Local run.
5. Docker build.
6. Required services.
7. Redis stream format.
8. Consumer group behavior.
9. ACK policy.
10. Retry/backoff behavior.
11. DLQ behavior.
12. Metrics.
13. Manual test scenario.
```

Local run example:

```bash
cd services/kitchen-scheduler-worker

go mod tidy
go test ./...
go run ./cmd/worker
```

Docker build example:

```bash
docker build -f services/kitchen-scheduler-worker/Dockerfile -t kitchen-scheduler-worker .
```

---

## 26. Definition of Done

Stage is complete when:

```text
1. services/kitchen-scheduler-worker exists.
2. Go module builds.
3. go test ./... passes.
4. Worker loads config from env.
5. Worker uses structured logging.
6. Worker exposes /health.
7. Worker exposes /metrics.
8. Worker connects to Redis.
9. Worker creates consumer group if missing.
10. Worker reads Redis Streams via XREADGROUP.
11. Worker parses Redis task messages.
12. Worker calls Fulfillment GET /internal/tasks/{task_id}.
13. Worker skips and XACKs terminal tasks.
14. Worker calls Fulfillment dispatch-readiness.
15. Worker delays retry when task is not ready.
16. Worker calls Kitchen dispatch-candidates.
17. Worker selects station by minimal visible backlog and busy slots.
18. Worker calls Kitchen KDS delivery.
19. Worker uses idempotency_key = {task_id}:dispatch:v1.
20. Worker calls Fulfillment mark-displayed.
21. Worker XACKs only after KDS delivery and mark-displayed succeed.
22. Worker retries temporary failures with backoff.
23. Worker sends message to DLQ after max attempts.
24. Worker calls Fulfillment dispatch-failed after DLQ.
25. Worker exports required Prometheus metrics.
26. Worker does not connect to PostgreSQL.
27. Worker does not set task in_progress.
28. Worker does not set task done.
29. Worker does not implement claim or complete.
30. README documents local run and manual test scenario.
```

---

## 27. Short instruction for the agent

Implement Stage 8 in services/kitchen-scheduler-worker.

Use Go 1.22+.

Implement:

```text
Redis consumer group
XREADGROUP
Fulfillment HTTP client
Kitchen/KDS HTTP client
dispatch algorithm
station selection
KDS delivery
mark-displayed
ACK policy
retry/backoff
DLQ
Prometheus metrics
structured logging
tests
Dockerfile
README
```

Critical ACK rule:

```text
XACK only after:
  KDS delivery succeeded
  Fulfillment mark-displayed succeeded
```

Use KDS idempotency key:

```text
{task_id}:dispatch:v1
```

Do not implement:

```text
claim
complete
start
done
station busy_slots changes
direct PostgreSQL access
order ready_for_pickup
Station Simulator
```
