# Kitchen Scheduler Worker

Go worker for Stage 8. It reads queued kitchen tasks from Redis Streams, asks Fulfillment whether a task can be dispatched, asks Kitchen Service for available KDS stations, delivers the task to KDS, then marks the task displayed in Fulfillment.

The worker is only a dispatcher. It does not claim tasks, complete tasks, cook tasks, write PostgreSQL directly, or set `in_progress` / `done`.

## Environment

| Variable | Default |
| --- | --- |
| `WORKER_ID` | `scheduler-worker-1` |
| `ENVIRONMENT` | `local` |
| `LOG_LEVEL` | `INFO` |
| `LOG_FORMAT` | `json` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `REDIS_STREAM_PATTERNS` | `stream:kitchen:*:station:*` |
| `REDIS_CONSUMER_GROUP` | `group:kitchen-scheduler-workers` |
| `FULFILLMENT_SERVICE_URL` | `http://localhost:8003` |
| `KITCHEN_SERVICE_URL` | `http://localhost:8001` |
| `STREAM_SCAN_INTERVAL_MS` | `500` |
| `XREAD_BLOCK_MS` | `5000` |
| `XREAD_COUNT` | `10` |
| `MAX_DISPATCH_ATTEMPTS` | `5` |
| `DISPATCH_BACKOFF_BASE_MS` | `1000` |
| `DISPATCH_BACKOFF_MAX_MS` | `30000` |
| `HTTP_TIMEOUT_MS` | `3000` |
| `PROMETHEUS_PORT` | `9090` |

## Local Run

```bash
cd services/kitchen-scheduler-worker
go mod tidy
go test ./...
go run ./cmd/worker
```

## Docker

```bash
docker build -f services/kitchen-scheduler-worker/Dockerfile -t kitchen-scheduler-worker .
```

## Redis Streams

Fulfillment publishes tasks to:

```text
stream:kitchen:{kitchen_id}:station:{station_type}
```

The worker scans `REDIS_STREAM_PATTERNS`, ignores `:dlq` streams, creates `REDIS_CONSUMER_GROUP` with `XGROUP CREATE ... MKSTREAM`, and reads new messages with `XREADGROUP`.

Required message fields: `task_id`, `order_id`, `kitchen_id`, `station_type`, `operation`, `menu_item_id`, `estimated_duration_seconds`. `attempt` defaults to `1`.

ACK policy: the worker `XACK`s only after KDS delivery succeeds and Fulfillment `mark-displayed` succeeds. Stale terminal tasks are acked without dispatch. Invalid messages are written to DLQ and acked.

## Retry And DLQ

Retry uses exponential backoff:

```text
min(DISPATCH_BACKOFF_BASE_MS * 2^(attempt - 1), DISPATCH_BACKOFF_MAX_MS)
```

Retries are re-enqueued into the same stream with `attempt + 1`. After `MAX_DISPATCH_ATTEMPTS`, the worker writes the message to:

```text
stream:kitchen:{kitchen_id}:station:{station_type}:dlq
```

Then it calls `POST /internal/tasks/{task_id}/dispatch-failed` and acks the original message.

## Metrics And Health

The worker exposes:

```text
GET /health
GET /metrics
```

Metrics include `dispatch_attempts_total`, `dispatch_success_total`, `dispatch_failed_total`, `dispatch_retries_total`, `dispatch_latency_seconds`, and `redis_dlq_messages_total`.

## Manual Scenario

1. Start Redis, PostgreSQL, MongoDB, Kitchen Service, Menu Service, and Fulfillment Service.
2. Seed kitchen, stations, menu item, recipe, and availability.
3. Create an order through Fulfillment.
4. Confirm queued Redis stream messages exist with `redis-cli KEYS 'stream:kitchen:*'`.
5. Start this worker.
6. Check that KDS receives the task and Fulfillment shows task status `displayed`.
7. Check metrics with `curl http://localhost:9090/metrics`.
