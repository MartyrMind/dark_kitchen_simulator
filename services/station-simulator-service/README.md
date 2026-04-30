# Station Simulator Service

Demo service for the dark kitchen project. It imitates station workers by polling Kitchen Service KDS tasks, claiming displayed tasks, sleeping for a scaled cooking duration, and completing tasks through the public KDS API.

## Boundary

The simulator only calls Kitchen Service:

```http
GET /kds/stations/{station_id}/tasks
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
```

It does not call Fulfillment Service directly, read Redis, or access PostgreSQL/MongoDB.

## Install

```bash
cd services/station-simulator-service
poetry install
```

## Environment

```bash
KITCHEN_SERVICE_URL=http://localhost:8001
HTTP_TIMEOUT_SECONDS=3
SIMULATOR_ENABLED=true
SIMULATOR_SPEED_FACTOR=60
SIMULATOR_POLL_INTERVAL_MS=1000
SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1,packaging_1:1
SIMULATOR_MIN_DURATION_FACTOR=0.7
SIMULATOR_MAX_DURATION_FACTOR=1.4
LOG_FORMAT=readable
```

Worker config uses `station_id:count` entries separated by commas. For example, `grill_1:2` starts `grill_1-worker-1` and `grill_1-worker-2`.

The speed factor scales cooking time:

```text
sleep_seconds = estimated_duration_seconds * random(min_factor, max_factor) / speed_factor
```

With `SIMULATOR_SPEED_FACTOR=60`, an 8 minute KDS task sleeps for about 8 seconds when the random factor is 1.0.

## Run Locally

```bash
cd services/station-simulator-service
poetry run uvicorn app.main:app --reload --port 8004
poetry run pytest
```

Useful endpoints:

```bash
curl http://localhost:8004/health
curl http://localhost:8004/metrics
curl http://localhost:8004/simulator/workers
```

## Docker

Build from the repository root:

```bash
docker build -f services/station-simulator-service/Dockerfile -t station-simulator-service .
docker run --rm -p 8004:8000 \
  -e KITCHEN_SERVICE_URL=http://host.docker.internal:8001 \
  -e SIMULATOR_ENABLED=true \
  -e SIMULATOR_WORKERS_CONFIG=grill_1:2,fryer_1:1 \
  station-simulator-service
```

In Compose, use `KITCHEN_SERVICE_URL=http://kitchen-service:8000` and usually put this service behind a `demo` profile.

## Metrics

`GET /metrics` exposes:

```text
simulator_claim_attempts_total{station_id,worker_id}
simulator_claim_success_total{station_id,worker_id}
simulator_claim_conflicts_total{station_id,worker_id,reason}
simulator_completed_tasks_total{station_id,worker_id}
simulator_task_duration_seconds{station_id,worker_id}
simulator_poll_errors_total{station_id,worker_id,reason}
simulator_active_workers
```

Metrics intentionally do not use `task_id`, `order_id`, or correlation IDs as labels.

Generic HTTP metrics are also exposed:

```text
http_requests_total
http_request_duration_seconds
```

## Manual Demo

1. Start Postgres, Redis, Mongo.
2. Start Kitchen Service, Menu Service, Fulfillment Service, and Kitchen Scheduler Worker.
3. Run migrations and seed kitchen, stations, menu, recipe steps, and availability.
4. Start this simulator with station IDs matching Kitchen Service station IDs.
5. Create an order through Fulfillment Service.

Expected flow:

```text
Fulfillment queues tasks -> Go worker dispatches to KDS -> simulator claims displayed task
-> Kitchen Service calls Fulfillment start -> simulator sleeps -> simulator completes task
-> Kitchen Service calls Fulfillment complete -> order reaches ready_for_pickup
```

## Troubleshooting

If the simulator sees no tasks, check that the scheduler worker is running, KDS has displayed tasks, and `SIMULATOR_WORKERS_CONFIG` uses actual station IDs.

If claims return `station_capacity_exceeded`, check station capacity, busy slots, and whether previous tasks are stuck in `claimed`.

If complete fails, check that Fulfillment Service is reachable from Kitchen Service and that the task is claimed by the same `station_worker_id`.

If an order does not reach `ready_for_pickup`, verify that all recipe steps were dispatched, every station type has simulator workers configured, and dependency-gated tasks are eventually displayed by the scheduler worker.
