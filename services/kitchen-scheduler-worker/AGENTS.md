# AGENTS.md — Kitchen Scheduler Worker

Go service. Отвечает за dispatch задач из Redis Streams в KDS.

## Назначение

```text
Redis Streams → Fulfillment snapshot/readiness → Kitchen dispatch candidates → KDS delivery → Fulfillment mark-displayed → XACK
```

## Обязательные правила

- Worker не готовит задачу.
- Worker не ставит `in_progress`.
- Worker не ставит `done`.
- Worker не делает `sleep(time_to_cook)`.
- Worker не читает и не пишет PostgreSQL напрямую.
- Worker ACK-ает Redis message только после успешной KDS delivery и успешного/idempotent `mark-displayed`.
- Если task уже `displayed`, `in_progress`, `done`, `cancelled` или `failed`, worker может XACK и skip.
- Если dependency не готова, worker делает delayed retry.
- Если кандидатов нет, worker делает retry/backoff.
- После max attempts worker отправляет задачу в DLQ и вызывает Fulfillment `dispatch-failed`.

## Station selection MVP

```text
1. status == available
2. health == ok
3. visible_backlog_size < visible_backlog_limit
4. выбрать min visible_backlog_size
5. при равенстве выбрать min busy_slots
```

## Структура Go-кода

```text
cmd/worker/main.go
internal/config/
internal/redis/
internal/fulfillment/
internal/kitchen/
internal/scheduler/
internal/retry/
internal/dlq/
internal/metrics/
internal/logging/
```

## Logs, events, metrics

Go logs должны быть structured через `slog` или `zerolog`.

Логи должны содержать:

- `worker_id`
- `stream`
- `message_id`
- `task_id`
- `order_id`
- `kitchen_id`
- `station_type`
- `station_id`, если выбран
- `attempt`
- `event`

Mongo events обычно пишет Fulfillment/Kitchen. Worker может вызывать Fulfillment endpoints, которые пишут audit events.

Metrics:

- `dispatch_attempts_total`
- `dispatch_success_total`
- `dispatch_failed_total`
- `dispatch_retries_total`
- `dispatch_latency_seconds`
- `redis_pending_messages`
- `redis_dlq_messages_total`

## Тесты

Минимум:

- skip non-dispatchable task;
- retry not-ready dependency;
- choose station by backlog/busy_slots;
- successful KDS delivery + mark-displayed + XACK;
- KDS success but mark-displayed temporary failure retries;
- max attempts sends to DLQ.
