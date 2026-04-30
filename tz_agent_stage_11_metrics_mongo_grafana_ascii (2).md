# Agent Task Spec: Stage 11 - Metrics, Mongo events, and Grafana

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
  KDS delivery and KdsTaskDisplayed event

Stage 7:
  fulfillment-service has internal task transition APIs
  task transition Mongo events

Stage 8:
  kitchen-scheduler-worker in Go
  dispatch from Redis Streams to KDS
  worker metrics

Stage 9:
  kitchen-service implements KDS claim and complete
  KDS and station events

Stage 10:
  station-simulator-service
  simulator metrics
```

This stage is cross-cutting observability.

The goal is to make the system demonstrable and diagnosable with:

```text
Prometheus metrics
MongoDB business/audit events
Grafana dashboards
report screenshots
```

---

## 1. Goal

Implement and standardize observability across the whole MVP.

At the end of this stage:

```text
1. All Python services expose GET /metrics.
2. Go worker exposes GET /metrics.
3. Prometheus scrapes all services.
4. Grafana has dashboards for the main MVP flows.
5. MongoDB contains event log for orders, tasks, KDS, stations, and audit events.
6. Important technical failures are written to app_audit_events.
7. Report screenshots are prepared.
```

Stage boundary:

```text
This stage improves observability only.
This stage must not rewrite business flows.
This stage must not change core task/order semantics.
This stage must not implement Kubernetes deployment.
This stage must not implement the final one-command demo script.
```

Kubernetes comes later.
Full Docker Compose demo orchestration comes later.

---

## 2. Scope

Implement:

```text
1. Extend dk-common with setup_metrics().
2. Add /metrics to all Python services:
   - kitchen-service
   - menu-service
   - fulfillment-service
   - station-simulator-service
3. Ensure Go worker exposes Prometheus metrics.
4. Standardize MongoDB domain events.
5. Add app_audit_events for important technical errors.
6. Add Prometheus scrape config.
7. Add Grafana provisioning.
8. Add Grafana dashboards.
9. Add basic smoke tests for /metrics and event writes.
10. Prepare screenshots directory and screenshot checklist.
11. Update READMEs.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- new business endpoints
- new status transitions
- new KDS claim/complete behavior
- new Redis dispatch behavior
- Station Simulator business changes
- Kubernetes manifests
- Helm charts
- service mesh
- Loki unless explicitly desired
- alerting rules unless simple and optional
- final run-demo.sh
- seed_demo_data.py
```

Optional:

```text
Loki is optional.
Alerts are optional.
```

Required:

```text
Prometheus metrics
Grafana dashboards
MongoDB events
```

---

## 4. Repository changes

Expected files and directories to add or update:

```text
libs/python/dk-common/
  dk_common/
    metrics.py
    mongo_events.py optional
  tests/
    test_metrics.py

services/kitchen-service/
  app/
    metrics/
      __init__.py optional
      business_metrics.py optional
  tests/
    test_metrics.py
    test_events.py

services/menu-service/
  app/
    metrics/
      __init__.py optional
  tests/
    test_metrics.py

services/fulfillment-service/
  app/
    metrics/
      __init__.py optional
      business_metrics.py optional
    events/
      order_events.py
      task_events.py
      audit_events.py
  tests/
    test_metrics.py
    test_events.py

services/station-simulator-service/
  app/
    metrics/
      metrics.py
  tests/
    test_metrics.py

services/kitchen-scheduler-worker/
  internal/
    metrics/
      metrics.go
  tests or package tests as already structured

deploy/
  compose/
    prometheus.yml
    grafana/
      provisioning/
        datasources/
          prometheus.yml
        dashboards/
          dashboards.yml
      dashboards/
        system-overview.json
        fulfillment.json
        scheduler-worker.json
        kds-kitchen.json
        simulator.json

docs/
  practice4/
    screenshots/
      README.md
```

If directories already exist, update them instead of duplicating.

---

## 5. dk-common metrics helper

### 5.1. Goal

Extend dk-common with reusable Prometheus helpers for Python services.

Create or update:

```text
libs/python/dk-common/dk_common/metrics.py
```

Required API:

```python
def setup_metrics(app, service_name: str) -> None:
    ...
```

Optional API:

```python
def get_metrics_router():
    ...

def record_http_request(
    service_name: str,
    method: str,
    path_template: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    ...
```

### 5.2. Required metrics

All Python services should expose generic HTTP metrics:

```text
http_requests_total{service, method, path, status}
http_request_duration_seconds{service, method, path}
```

Metric types:

```text
http_requests_total -> Counter
http_request_duration_seconds -> Histogram
```

Allowed labels:

```text
service
method
path
status
```

Do not use these as labels:

```text
order_id
task_id
request_id
correlation_id
redis_message_id
```

### 5.3. Path template rule

The path label must be a route template, not a raw URL path.

Good:

```text
/orders/{order_id}
,kds/stations/{station_id}/tasks
/internal/tasks/{task_id}/complete
```

Bad:

```text
/orders/14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e
/kds/stations/7a7fef8e-560f-4d77-95ab-758d9a4ae4b8/tasks
```

Implementation hint:

```text
For FastAPI, use request.scope["route"].path if available.
Fallback to request.url.path only for unknown routes.
```

### 5.4. /metrics endpoint

setup_metrics() must add:

```http
GET /metrics
```

It should return Prometheus text format.

Use:

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
```

Example response:

```text
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
...
```

### 5.5. Dependencies

Add to dk-common if not present:

```toml
prometheus-client = "^0.20.0"
```

### 5.6. Tests for dk-common

Add tests:

```text
setup_metrics adds /metrics endpoint
GET /metrics returns 200
GET /metrics contains http_requests_total
GET /metrics contains http_request_duration_seconds
path label uses route template
high-cardinality route params are not used in path label
```

---

## 6. Add /metrics to Python services

Update each Python service app startup:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
```

Example:

```python
from dk_common.metrics import setup_metrics

setup_metrics(app, service_name=settings.service_name)
```

Required behavior:

```text
GET /health works.
GET /metrics works.
HTTP requests are counted.
HTTP request duration is recorded.
```

Do not remove existing custom service metrics.
If custom metrics already exist, keep them and make them visible through the same /metrics endpoint.

---

## 7. Service-specific metrics

### 7.1. Fulfillment Service metrics

Expose:

```text
orders_created_total{kitchen_id}
orders_cancelled_total{kitchen_id}
orders_ready_total{kitchen_id}
orders_handed_off_total{kitchen_id}
orders_delayed_total{kitchen_id}

tasks_queued_total{kitchen_id, station_type}
tasks_displayed_total{kitchen_id, station_type}
tasks_started_total{kitchen_id, station_type}
tasks_completed_total{kitchen_id, station_type}
tasks_failed_total{kitchen_id, station_type}

task_actual_duration_seconds{kitchen_id, station_type}
task_delay_seconds{kitchen_id, station_type}
```

Metric types:

```text
orders_*_total -> Counter
tasks_*_total -> Counter
task_actual_duration_seconds -> Histogram
task_delay_seconds -> Histogram
```

Increment points:

```text
orders_created_total:
  when POST /orders creates order

tasks_queued_total:
  when task is successfully published to Redis and moved to queued

tasks_displayed_total:
  when mark-displayed succeeds

tasks_started_total:
  when start succeeds

tasks_completed_total:
  when complete succeeds

tasks_failed_total:
  when task is failed

orders_ready_total:
  when order moves to ready_for_pickup
```

Labels:

```text
kitchen_id
station_type
```

Do not label by:

```text
order_id
task_id
correlation_id
```

### 7.2. Kitchen Service / KDS metrics

Expose:

```text
kds_visible_backlog_size{kitchen_id, station_id, station_type}
kds_claim_attempts_total{kitchen_id, station_id, station_type}
kds_claim_success_total{kitchen_id, station_id, station_type}
kds_claim_conflicts_total{kitchen_id, station_id, station_type, reason}
station_busy_slots{kitchen_id, station_id, station_type}
station_capacity{kitchen_id, station_id, station_type}
station_utilization_ratio{kitchen_id, station_id, station_type}
```

Metric types:

```text
kds_visible_backlog_size -> Gauge
kds_claim_attempts_total -> Counter
kds_claim_success_total -> Counter
kds_claim_conflicts_total -> Counter
station_busy_slots -> Gauge
station_capacity -> Gauge
station_utilization_ratio -> Gauge
```

Update points:

```text
KDS delivery:
  update visible backlog

KDS claim attempt:
  increment kds_claim_attempts_total

KDS claim success:
  increment kds_claim_success_total
  update busy slots, capacity, utilization

KDS claim conflict:
  increment kds_claim_conflicts_total with reason

KDS complete:
  update busy slots, capacity, utilization
  update visible backlog
```

If real-time gauges are hard:

```text
It is acceptable to update gauges during delivery, claim, complete, capacity/status changes.
```

### 7.3. Kitchen Scheduler Worker metrics

Ensure Go worker exposes:

```text
dispatch_attempts_total{kitchen_id, station_type}
dispatch_success_total{kitchen_id, station_type, station_id}
dispatch_failed_total{kitchen_id, station_type, reason}
dispatch_retries_total{kitchen_id, station_type, reason}
dispatch_latency_seconds{kitchen_id, station_type}
redis_pending_messages{kitchen_id, station_type}
redis_dlq_messages_total{kitchen_id, station_type}
```

Metric types:

```text
dispatch_*_total -> Counter
dispatch_latency_seconds -> Histogram
redis_pending_messages -> Gauge
redis_dlq_messages_total -> Counter
```

If redis_pending_messages is expensive:

```text
Update periodically.
Do not calculate on every message if it hurts performance.
```

### 7.4. Station Simulator metrics

Ensure simulator exposes:

```text
simulator_claim_attempts_total{station_id, worker_id}
simulator_claim_success_total{station_id, worker_id}
simulator_claim_conflicts_total{station_id, worker_id, reason}
simulator_completed_tasks_total{station_id, worker_id}
simulator_task_duration_seconds{station_id, worker_id}
simulator_poll_errors_total{station_id, worker_id, reason}
simulator_active_workers
```

Metric types:

```text
simulator_claim_attempts_total -> Counter
simulator_claim_success_total -> Counter
simulator_claim_conflicts_total -> Counter
simulator_completed_tasks_total -> Counter
simulator_task_duration_seconds -> Histogram
simulator_poll_errors_total -> Counter
simulator_active_workers -> Gauge
```

### 7.5. Menu Service metrics

Menu Service may only need generic HTTP metrics.

Optional business metrics:

```text
menu_items_created_total
recipe_steps_created_total
menu_availability_updates_total
```

This is optional.
Do not spend too much time on Menu-specific dashboards.

---

## 8. MongoDB event log standardization

### 8.1. Collections

Use these collections:

```text
order_events
task_events
kds_events
station_events
app_audit_events
```

### 8.2. Common event fields

All events should include:

```text
event_type
service
created_at
correlation_id
payload
```

When applicable, also include:

```text
order_id
task_id
kitchen_id
station_id
station_type
kds_task_id
station_worker_id
```

Example base shape:

```json
{
  "event_type": "TaskCompleted",
  "service": "fulfillment-service",
  "correlation_id": "corr_123",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "station_type": "grill",
  "payload": {
    "actual_duration_seconds": 360,
    "delay_seconds": 0
  },
  "created_at": "2026-04-30T10:08:00Z"
}
```

### 8.3. Event writer behavior

Required behavior:

```text
If MongoDB event write fails:
  log error
  write app_audit_events if possible for critical failures
  do not fail the main business operation only because event write failed
```

Exception:

```text
If the operation itself is an audit-only operation, return error as appropriate.
```

For MVP:

```text
Business state in PostgreSQL is source of truth.
MongoDB is event/audit history.
```

### 8.4. dk-common mongo helper optional

If useful, add a generic helper:

```text
libs/python/dk-common/dk_common/mongo_events.py
```

Allowed in dk-common:

```text
generic Mongo connection helper
generic insert_event(collection, event) helper
timestamp normalization
correlation_id injection helper
```

Forbidden in dk-common:

```text
OrderCreated semantics
TaskCompleted semantics
KdsTaskClaimed semantics
station business logic
event_type-specific payload builders
```

Event-specific builders must live in service code.

---

## 9. Required domain events

### 9.1. Fulfillment Service events

Collections:

```text
order_events
task_events
app_audit_events
```

Required order events:

```text
OrderCreated
KitchenTasksCreated
OrderCookingStarted
OrderReadyForPickup
OrderHandedOff if handoff endpoint exists
OrderCancelled if cancel endpoint exists
OrderFailed if implemented
```

Required task events:

```text
TaskQueued
TaskDisplayed
TaskStarted
TaskCompleted
TaskDispatchRetried if retry endpoint exists
TaskDispatchFailed
TaskFailed if implemented
TaskCancelled if implemented
```

Minimum required for Stage 11 if previous stages exist:

```text
OrderCreated
KitchenTasksCreated
TaskQueued
TaskDisplayed
TaskStarted
TaskCompleted
TaskDispatchFailed
OrderReadyForPickup
```

### 9.2. Kitchen Service events

Collections:

```text
kds_events
station_events
app_audit_events
```

Required KDS events:

```text
KdsTaskDisplayed
KdsTaskClaimed
KdsTaskClaimRejected
KdsTaskCompleted
KdsTaskFailed if fail endpoint exists
KdsTaskRemoved if implemented
```

Required station events:

```text
StationCreated
StationStatusChanged
StationCapacityChanged
StationBusySlotOccupied
StationBusySlotReleased
```

Minimum required for Stage 11:

```text
StationCreated
StationStatusChanged
StationCapacityChanged
KdsTaskDisplayed
KdsTaskClaimed
KdsTaskClaimRejected
KdsTaskCompleted
StationBusySlotOccupied
StationBusySlotReleased
```

### 9.3. Worker audit events

Kitchen Scheduler Worker is Go.
It may not write to MongoDB directly in this stage if not already designed for it.

Required minimum:

```text
Worker logs dispatch failures in structured logs.
Fulfillment Service writes TaskDispatchFailed when worker calls dispatch-failed.
```

Optional:

```text
Worker writes app_audit_events directly to MongoDB for:
  RedisMessageMovedToDlq
  ExternalServiceUnavailable
  KdsDeliveryFailed
```

If implemented, keep it simple and document it.

### 9.4. app_audit_events

Use app_audit_events for important technical events that affect order execution.

Required audit event types:

```text
DispatchRetried
DispatchFailed
FulfillmentCallbackFailed
KdsDeliveryFailed
RedisMessageMovedToDlq
ExternalServiceUnavailable
MongoEventWriteFailed
```

Event shape:

```json
{
  "event_type": "ExternalServiceUnavailable",
  "service": "kitchen-service",
  "correlation_id": "corr_123",
  "order_id": "14cb4b0a-0100-4c6d-bb1f-6ce78ea45c8e",
  "task_id": "8f39f9fc-9c17-4995-8767-fd7e62c44852",
  "payload": {
    "external_service": "fulfillment-service",
    "operation": "POST /internal/tasks/{task_id}/start",
    "error": "timeout"
  },
  "created_at": "2026-04-30T10:02:00Z"
}
```

Do not write every debug or info log to MongoDB.

MongoDB is not a technical log sink.

---

## 10. Correlation ID consistency

Every event and log should include correlation_id when available.

Flows to verify:

```text
Fulfillment Service -> Menu Service
Fulfillment Service -> Kitchen Service
Kitchen Scheduler Worker -> Fulfillment Service
Kitchen Scheduler Worker -> Kitchen Service / KDS
Kitchen Service / KDS -> Fulfillment Service
Station Simulator -> Kitchen Service / KDS
```

Requirements:

```text
1. Incoming external request gets X-Correlation-ID.
2. If missing, service generates it.
3. Internal HTTP calls propagate X-Correlation-ID.
4. MongoDB events include correlation_id.
5. Structured logs include correlation_id.
6. HTTP responses include X-Correlation-ID.
```

Prometheus rule:

```text
Do not use correlation_id as a metric label.
```

---

## 11. Prometheus configuration

Create or update:

```text
deploy/compose/prometheus.yml
```

Required scrape jobs:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "kitchen-service"
    metrics_path: /metrics
    static_configs:
      - targets: ["kitchen-service:8000"]

  - job_name: "menu-service"
    metrics_path: /metrics
    static_configs:
      - targets: ["menu-service:8000"]

  - job_name: "fulfillment-service"
    metrics_path: /metrics
    static_configs:
      - targets: ["fulfillment-service:8000"]

  - job_name: "station-simulator-service"
    metrics_path: /metrics
    static_configs:
      - targets: ["station-simulator-service:8000"]

  - job_name: "kitchen-scheduler-worker"
    metrics_path: /metrics
    static_configs:
      - targets: ["kitchen-scheduler-worker:9090"]
```

If simulator metrics run on a separate port, adjust target:

```text
station-simulator-service:9100
```

Use the actual service ports from the repo.

Do not use localhost in container scrape targets.

---

## 12. Grafana provisioning

Create or update:

```text
deploy/compose/grafana/provisioning/datasources/prometheus.yml
```

Example:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

Create or update:

```text
deploy/compose/grafana/provisioning/dashboards/dashboards.yml
```

Example:

```yaml
apiVersion: 1

providers:
  - name: "Dark Kitchen Dashboards"
    orgId: 1
    folder: "Dark Kitchen"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
```

Dashboards should be JSON files in:

```text
deploy/compose/grafana/dashboards/
```

---

## 13. Required Grafana dashboards

Create at least five dashboards.

### 13.1. System overview dashboard

File:

```text
system-overview.json
```

Panels:

```text
HTTP RPS by service
HTTP error rate by service
p95 HTTP latency by service
up status by job
```

Example PromQL:

```promql
sum by (service) (rate(http_requests_total[1m]))
```

```promql
sum by (service) (rate(http_requests_total{status=~"5.."}[1m]))
```

```promql
histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))
```

```promql
up
```

### 13.2. Fulfillment dashboard

File:

```text
fulfillment.json
```

Panels:

```text
orders created rate
orders ready rate
tasks queued/displayed/started/completed rate
task actual duration p95
task delay p95
failed tasks rate
```

Example PromQL:

```promql
sum(rate(orders_created_total[5m]))
```

```promql
sum(rate(orders_ready_total[5m]))
```

```promql
sum by (station_type) (rate(tasks_completed_total[5m]))
```

```promql
histogram_quantile(0.95, sum by (station_type, le) (rate(task_actual_duration_seconds_bucket[5m])))
```

```promql
histogram_quantile(0.95, sum by (station_type, le) (rate(task_delay_seconds_bucket[5m])))
```

### 13.3. Scheduler worker dashboard

File:

```text
scheduler-worker.json
```

Panels:

```text
dispatch attempts
dispatch success
dispatch failures by reason
dispatch retries by reason
dispatch latency p95
Redis pending messages
DLQ messages
```

Example PromQL:

```promql
sum by (station_type) (rate(dispatch_attempts_total[5m]))
```

```promql
sum by (station_type, station_id) (rate(dispatch_success_total[5m]))
```

```promql
sum by (reason) (rate(dispatch_failed_total[5m]))
```

```promql
histogram_quantile(0.95, sum by (station_type, le) (rate(dispatch_latency_seconds_bucket[5m])))
```

### 13.4. KDS / Kitchen dashboard

File:

```text
kds-kitchen.json
```

Panels:

```text
KDS visible backlog by station
claim attempts
claim success
claim conflicts by reason
station busy slots
station capacity
station utilization ratio
```

Example PromQL:

```promql
kds_visible_backlog_size
```

```promql
sum by (station_id) (rate(kds_claim_success_total[5m]))
```

```promql
sum by (reason) (rate(kds_claim_conflicts_total[5m]))
```

```promql
station_busy_slots
```

```promql
station_utilization_ratio
```

### 13.5. Simulator dashboard

File:

```text
simulator.json
```

Panels:

```text
simulator active workers
simulator claim attempts
simulator claim conflicts
simulator completed tasks
simulator task duration p95
simulator poll errors
```

Example PromQL:

```promql
simulator_active_workers
```

```promql
sum by (station_id, worker_id) (rate(simulator_claim_attempts_total[5m]))
```

```promql
sum by (reason) (rate(simulator_claim_conflicts_total[5m]))
```

```promql
sum by (station_id) (rate(simulator_completed_tasks_total[5m]))
```

```promql
histogram_quantile(0.95, sum by (station_id, le) (rate(simulator_task_duration_seconds_bucket[5m])))
```

---

## 14. Docker Compose notes

This stage can update compose enough for observability.

If deploy/compose/docker-compose.yml exists, verify or add:

```yaml
services:
  prometheus:
    image: prom/prometheus:v2.54.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:11.1.0
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
```

If compose already has prometheus/grafana, update it instead of duplicating.

Do not implement the full demo orchestration in this stage.
Stage 12 will handle full Docker Compose demo.

---

## 15. Tests and smoke checks

### 15.1. Unit tests

Required:

```text
dk-common setup_metrics tests
event builder tests for each service
metric increment tests for service-specific metrics where simple
correlation_id included in event payloads
```

### 15.2. Component tests

For each Python service:

```text
GET /metrics returns 200
GET /metrics contains http_requests_total
GET /metrics contains service-specific metrics if any
```

For Go worker:

```text
GET /metrics returns 200
metrics include dispatch_attempts_total or registered worker metrics
```

### 15.3. Mongo event tests

Use fake Mongo writer or test Mongo instance.

Required checks:

```text
OrderCreated event is written on order creation
TaskQueued event is written when task is queued
TaskDisplayed event is written when mark-displayed succeeds
TaskStarted event is written when start succeeds
TaskCompleted event is written when complete succeeds
KdsTaskDisplayed event is written on KDS delivery
KdsTaskClaimed event is written on claim
KdsTaskCompleted event is written on complete
StationBusySlotOccupied event is written on claim
StationBusySlotReleased event is written on complete
```

### 15.4. Prometheus smoke test

If compose can run services:

```text
GET http://localhost:9090/-/ready returns 200
GET http://localhost:9090/api/v1/targets returns active targets
targets for all services are UP
```

### 15.5. Grafana smoke test

If compose can run Grafana:

```text
GET http://localhost:3000 returns 200 or login page
dashboards are provisioned
Prometheus datasource is configured
```

Manual check is acceptable for Grafana.

---

## 16. Screenshots for report

Create:

```text
docs/practice4/screenshots/README.md
```

Add checklist:

```text
1. Prometheus targets page with all services UP.
2. Grafana System overview dashboard.
3. Grafana Fulfillment dashboard.
4. Grafana Scheduler worker dashboard.
5. Grafana KDS / Kitchen dashboard.
6. Grafana Simulator dashboard.
7. MongoDB order_events query result.
8. MongoDB task_events query result.
9. MongoDB kds_events query result.
10. MongoDB station_events query result.
11. MongoDB app_audit_events example if available.
```

Do not generate screenshots automatically unless the repo already has tooling for it.

The goal of this stage is to prepare screenshot locations and checklist.

---

## 17. README updates

Update root README and relevant service READMEs.

Root README should include:

```text
1. Observability overview.
2. How to start Prometheus.
3. How to start Grafana.
4. Grafana default credentials if using local defaults.
5. Where dashboards are stored.
6. How to inspect MongoDB events.
7. How to inspect /metrics endpoints manually.
```

Service READMEs should mention:

```text
GET /metrics
service-specific metrics
Mongo events emitted by the service
```

Example commands:

```bash
curl http://localhost:8000/metrics
curl http://localhost:9090/api/v1/targets
```

Mongo shell examples:

```bash
mongosh mongodb://localhost:27017/dark_kitchen_events
db.order_events.find().sort({created_at: -1}).limit(5)
db.task_events.find().sort({created_at: -1}).limit(5)
db.kds_events.find().sort({created_at: -1}).limit(5)
db.station_events.find().sort({created_at: -1}).limit(5)
db.app_audit_events.find().sort({created_at: -1}).limit(5)
```

---

## 18. Acceptance checklist

The stage is complete when:

```text
1. dk-common has setup_metrics().
2. dk-common tests for metrics pass.
3. kitchen-service exposes GET /metrics.
4. menu-service exposes GET /metrics.
5. fulfillment-service exposes GET /metrics.
6. station-simulator-service exposes GET /metrics.
7. kitchen-scheduler-worker exposes GET /metrics.
8. Python services export generic HTTP metrics.
9. Fulfillment exports order and task metrics.
10. Kitchen Service exports KDS and station metrics.
11. Worker exports dispatch metrics.
12. Simulator exports simulator metrics.
13. MongoDB has order_events.
14. MongoDB has task_events.
15. MongoDB has kds_events.
16. MongoDB has station_events.
17. MongoDB has app_audit_events for important technical errors.
18. Events include service, event_type, created_at, correlation_id, payload.
19. Prometheus scrape config includes all services.
20. Prometheus targets show services as UP in local compose environment.
21. Grafana datasource is provisioned.
22. Grafana dashboards are provisioned.
23. Required dashboards exist as JSON files.
24. Screenshots directory and checklist exist.
25. README documents observability usage.
26. No high-cardinality labels are added for task_id, order_id, request_id, or correlation_id.
27. MongoDB is not used as a sink for every debug/info application log.
```

---

## 19. Short instruction for the agent

Implement Stage 11: metrics, Mongo events, and Grafana.

Add to dk-common:

```text
setup_metrics()
generic HTTP metrics middleware
/metrics helper
```

Add /metrics to:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
kitchen-scheduler-worker
```

Standardize MongoDB events:

```text
order_events
task_events
kds_events
station_events
app_audit_events
```

Add Prometheus config:

```text
deploy/compose/prometheus.yml
```

Add Grafana provisioning and dashboards:

```text
deploy/compose/grafana/provisioning
deploy/compose/grafana/dashboards
```

Create dashboards:

```text
system-overview.json
fulfillment.json
scheduler-worker.json
kds-kitchen.json
simulator.json
```

Do not implement:

```text
Kubernetes
full demo script
new business endpoints
new task transitions
new Redis worker behavior
Loki unless optional and explicitly requested
```
