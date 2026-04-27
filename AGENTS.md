# AGENTS.md

Инструкции для AI coding agents, работающих с репозиторием `dark-kitchen-fulfillment`.

## Назначение проекта

Проект — учебная микросервисная backend-система для dark kitchen.

Ключевой бизнес-flow:

```text
POST /orders
  → Fulfillment создает order + kitchen_tasks
  → Fulfillment публикует tasks в Redis Streams
  → Go Kitchen Scheduler Worker выбирает station_id
  → Worker доставляет task в KDS внутри Kitchen Service
  → Fulfillment фиксирует queued → displayed
  → Station Simulator / worker делает claim
  → Kitchen Service вызывает Fulfillment displayed → in_progress
  → Station Simulator / worker делает complete
  → Kitchen Service вызывает Fulfillment in_progress → done
  → Fulfillment переводит order в ready_for_pickup
```

## Архитектурные границы

### Fulfillment Service

Владеет:

- `orders`
- `order_items`
- `kitchen_tasks`
- `task_dependencies`
- глобальными бизнес-статусами заказов и kitchen tasks
- переходом заказа в `ready_for_pickup`

Только Fulfillment Service может менять глобальные статусы kitchen task:

```text
created, queued, displayed, in_progress, done, failed, retrying, cancelled
```

Нельзя:

- писать в таблицы Kitchen Service;
- напрямую изменять KDS state;
- импортировать Python-код из других сервисов.

### Kitchen Service

Владеет:

- `kitchens`
- `stations`
- `station capacity`
- `busy_slots`
- `kds_station_tasks`
- KDS API: `claim`, `complete`, `fail`

Нельзя:

- напрямую писать в `fulfillment.kitchen_tasks`;
- самостоятельно переводить order в `ready_for_pickup`;
- хранить глобальные бизнес-статусы как источник истины.

### Menu Service

Владеет:

- `menu_items`
- `kitchen_menu_availability`
- `recipe_steps`

Нельзя:

- создавать orders;
- создавать kitchen tasks;
- dispatch-ить задачи в KDS.

### Kitchen Scheduler Worker

Go-сервис. Делает только dispatch:

```text
Redis Streams → Fulfillment snapshot/readiness → Kitchen dispatch candidates → KDS delivery → Fulfillment mark-displayed → XACK
```

Нельзя:

- ставить `in_progress`;
- ставить `done`;
- выполнять `sleep(time_to_cook)`;
- напрямую читать/писать PostgreSQL сервисов.

### Station Simulator Service

Demo-сервис. Имитирует работников станции.

Работает только через KDS API Kitchen Service:

```text
GET /kds/stations/{station_id}/tasks
POST /kds/stations/{station_id}/tasks/{task_id}/claim
POST /kds/stations/{station_id}/tasks/{task_id}/complete
```

## Структура репозитория

Ожидаемая структура:

```text
dark-kitchen-fulfillment/
  AGENTS.md
  README.md
  Makefile
  .env.example

  docs/
    practice1/
    practice2/
    practice3/
    practice4/

  services/
    kitchen-service/
    menu-service/
    fulfillment-service/
    kitchen-scheduler-worker/
    station-simulator-service/

  libs/
    python/
      dk-common/

  contracts/
    openapi/
    schemas/

  deploy/
    compose/
    k8s/
    monitoring/

  tests/
    integration/
    e2e/
```

## Dependency management

### Python local development

Для локальной разработки Python-сервисов используется Poetry.

У каждого Python-сервиса должен быть собственный `pyproject.toml` и собственный lock-файл:

```text
services/kitchen-service/pyproject.toml
services/menu-service/pyproject.toml
services/fulfillment-service/pyproject.toml
services/station-simulator-service/pyproject.toml
```

Общая библиотека подключается как path dependency:

```toml
[tool.poetry.dependencies]
dk-common = { path = "../../libs/python/dk-common", develop = true }
```

### Python containers

Для контейнеров используется `uv`.

Dockerfile Python-сервиса должен уметь установить зависимости через `uv`, но не должен требовать глобального root Python-проекта.

### Go

`kitchen-scheduler-worker` имеет собственный `go.mod`.

Не добавляй Go-код в Python-пакеты и не создавай общий root `go.mod`, пока это не требуется.

## Общая Python-библиотека `libs/python/dk-common`

Разрешено класть в `dk-common` только технические, не доменные вещи:

- настройка Loguru;
- middleware request id / correlation id;
- базовые settings helpers;
- Prometheus helpers;
- healthcheck helpers;
- common HTTP client wrapper;
- общие исключения инфраструктурного уровня;
- helper для Mongo event publisher без знания конкретных доменных событий.

Нельзя класть в `dk-common`:

- SQLAlchemy-модели сервисов;
- бизнес-логику заказов;
- бизнес-логику KDS;
- enum статусов как единственный источник истины;
- репозитории сервисов;
- use cases сервисов;
- клиенты конкретных сервисов, если они создают жесткую связанность.

Правило:

> `dk-common` не должен знать, что такое заказ, кухня, станция, рецепт или KDS task.

## MongoDB, logs, metrics

Не смешивать три разных потока наблюдаемости.

### PostgreSQL

Хранит текущее состояние:

- orders;
- kitchen_tasks;
- kitchens;
- stations;
- menu_items;
- kds_station_tasks.

### MongoDB

Хранит бизнес/audit-события:

- `OrderCreated`
- `TaskQueued`
- `TaskDisplayed`
- `TaskStarted`
- `TaskCompleted`
- `KdsTaskClaimed`
- `KdsTaskCompleted`
- `OrderReadyForPickup`
- `DispatchFailed`

MongoDB — не основное хранилище application logs.

### Application logs

Пишутся через Loguru в stdout/stderr контейнера.

Логи должны быть structured JSON-friendly и содержать:

- `service`
- `environment`
- `request_id`
- `correlation_id`
- `order_id`, если есть
- `task_id`, если есть
- `station_id`, если есть
- `event`
- `level`

### Metrics

Prometheus metrics доступны на `/metrics` каждого сервиса.

Grafana в MVP обязана показывать метрики. Логи в Grafana допустимы как расширение через Loki, но не обязательны для MVP.

## Тестовая стратегия

### Unit tests

Тестируют чистую бизнес-логику внутри сервиса без сетевых вызовов.

### Component tests

Тестируют один сервис с его БД/Redis/Mongo, но внешние сервисы заменяются fake/mock HTTP server.

### Integration tests

Запускают несколько реальных сервисов через Docker Compose или Testcontainers.

Минимальные integration flows:

- Fulfillment → Menu;
- Fulfillment → Kitchen;
- Fulfillment → Redis Streams;
- Worker → Fulfillment + Kitchen;
- Kitchen KDS → Fulfillment.

### End-to-end tests

Проверяют полный бизнес-flow:

```text
seed kitchen/stations/menu/recipe
POST /orders
wait tasks queued
wait worker dispatch
GET KDS station tasks
claim
complete
wait order ready_for_pickup
assert Mongo events
assert Prometheus metrics available
```

## Общие правила для AI-изменений

Перед изменением кода:

1. Определи сервис-владельца данных.
2. Проверь, не нарушает ли изменение границы сервисов.
3. Если добавляется публичный API — обнови OpenAPI/contract.
4. Если меняется БД — добавь миграцию.
5. Если добавляется бизнес-переход — добавь event в Mongo audit log.
6. Если добавляется важный процесс — добавь metric.
7. Если добавляется endpoint — добавь unit/component test.
8. Если меняется cross-service flow — добавь integration или e2e test.

Не делай:

- прямые импорты из одного сервиса в другой;
- общий root Python package для всех сервисов;
- запись в чужую БД;
- `sys.path.append(...)` для доступа к `libs`;
- скрытые зависимости между сервисами через shared code;
- business state в MongoDB вместо PostgreSQL.
