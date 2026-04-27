# AGENTS.md — Kitchen Service

Kitchen Service управляет кухнями, станциями, capacity и KDS API.

## Владеет данными

- `kitchens`
- `stations`
- `kds_station_tasks`
- `station capacity`
- `busy_slots`
- локальные KDS-статусы

## Основные API

Public API:

```text
POST /kitchens
GET /kitchens
GET /kitchens/{kitchen_id}
POST /kitchens/{kitchen_id}/stations
GET /kitchens/{kitchen_id}/stations
PATCH /stations/{station_id}/capacity
PATCH /stations/{station_id}/status
```

KDS API:

```text
GET /kds/stations/{station_id}/tasks
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
POST /kds/stations/{station_id}/tasks/{task_id}/fail
```

Internal API for Scheduler Worker:

```text
GET /internal/kds/dispatch-candidates
POST /internal/kds/stations/{station_id}/tasks
```

## Обязательные правила

- Capacity проверяется на `claim`, а не на dispatch.
- Dispatch только показывает задачу в KDS.
- `claim` должен атомарно проверять `busy_slots < capacity`.
- Двойной claim одной задачи должен возвращать `409 task_already_claimed`.
- Превышение capacity должно возвращать `409 station_capacity_exceeded`.
- После успешного claim Kitchen Service вызывает Fulfillment `/internal/tasks/{task_id}/start`.
- После successful complete Kitchen Service вызывает Fulfillment `/internal/tasks/{task_id}/complete`.
- Kitchen Service не пишет напрямую в таблицы Fulfillment Service.

## Логи, события, метрики

Loguru logs:

- request received;
- KDS delivery;
- claim attempt/success/conflict;
- complete attempt/success/failure;
- capacity conflicts.

Mongo events:

- `KdsTaskDisplayed`
- `KdsTaskClaimed`
- `KdsTaskClaimRejected`
- `KdsTaskCompleted`
- `StationBusySlotOccupied`
- `StationBusySlotReleased`

Metrics:

- `kds_visible_backlog_size`
- `kds_claim_attempts_total`
- `kds_claim_success_total`
- `kds_claim_conflicts_total`
- `station_busy_slots`
- `station_capacity`
- `station_utilization_ratio`

## Тесты

Минимум:

- создание кухни;
- создание станции;
- dispatch idempotency;
- claim success;
- double claim conflict;
- capacity exceeded;
- complete releases busy slot.
