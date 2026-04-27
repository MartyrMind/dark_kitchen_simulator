# SKILLS.md — Python Services

Повторяемые инструкции для AI coding agents при работе с Python-сервисами проекта.

Python-сервисы:

- `services/kitchen-service`
- `services/menu-service`
- `services/fulfillment-service`
- `services/station-simulator-service`

Локальная разработка: Poetry.
Контейнеры: uv.
Общая техническая библиотека: `libs/python/dk-common`.

---

# Skill: создать новый Python-сервис

Используй этот skill, когда пользователь просит создать новый Python-сервис в монорепе.

## Входные данные

Нужно знать:

- имя сервиса;
- назначение сервиса;
- нужен ли PostgreSQL;
- нужен ли MongoDB;
- нужен ли Redis;
- какие внешние сервисы он вызывает;
- какие endpoints нужны в MVP.

Если данных не хватает, сделай разумное MVP-допущение и явно запиши его в README сервиса.

## Создай структуру

```text
services/<service-name>/
  AGENTS.md
  README.md
  Dockerfile
  pyproject.toml
  poetry.lock
  app/
    __init__.py
    main.py
    api/
      __init__.py
      routes.py
    core/
      __init__.py
      config.py
      logging.py
    db/
      __init__.py
      session.py
    models/
      __init__.py
    schemas/
      __init__.py
    services/
      __init__.py
    repositories/
      __init__.py
    metrics/
      __init__.py
  tests/
    __init__.py
    test_health.py
```

Если нужен PostgreSQL:

```text
  alembic/
  alembic.ini
```

## pyproject.toml с Poetry

Минимальный шаблон:

```toml
[tool.poetry]
name = "<service-name>"
version = "0.1.0"
description = "Dark Kitchen <service-name>"
authors = ["Dark Kitchen Team"]
packages = [{ include = "app" }]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
uvicorn = { extras = ["standard"], version = "^0.30.0" }
pydantic = "^2.8.0"
pydantic-settings = "^2.4.0"
loguru = "^0.7.2"
prometheus-client = "^0.20.0"
httpx = "^0.27.0"
dk-common = { path = "../../libs/python/dk-common", develop = true }

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
ruff = "^0.6.0"
mypy = "^1.11.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

Если нужен PostgreSQL, добавь:

```toml
sqlalchemy = { extras = ["asyncio"], version = "^2.0.0" }
asyncpg = "^0.29.0"
alembic = "^1.13.0"
```

Если нужен MongoDB:

```toml
motor = "^3.5.0"
```

Если нужен Redis:

```toml
redis = "^5.0.0"
```

## main.py

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.api.routes import router
from app.core.config import settings
from dk_common.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(service_name=settings.service_name)

    app = FastAPI(title=settings.service_name)
    app.include_router(router)
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
```

## Health endpoint

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

## Dockerfile с uv

Docker build context должен быть корнем репозитория, если сервис использует `libs/python/dk-common`.

```dockerfile
FROM python:3.11-slim AS runtime

WORKDIR /repo

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY libs/python/dk-common libs/python/dk-common
COPY services/<service-name> services/<service-name>

WORKDIR /repo/services/<service-name>

RUN uv pip install --system .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Definition of done

- сервис запускается локально через Poetry;
- сервис собирается в Docker через uv;
- есть `/health`;
- есть `/metrics`;
- есть test на `/health`;
- есть README;
- нет импортов из других сервисов.

---

# Skill: добавить endpoint в Python-сервис

Используй этот skill, когда пользователь просит добавить endpoint в существующий Python-сервис.

## Порядок работы

1. Определи владельца данных.
2. Найди правильный service-level `AGENTS.md`.
3. Добавь Pydantic schemas.
4. Добавь route в `app/api`.
5. Добавь service/use-case слой.
6. Добавь repository слой, если нужен доступ к БД.
7. Добавь миграцию Alembic, если меняется модель данных.
8. Добавь Mongo event publisher, если endpoint меняет бизнес-состояние.
9. Добавь Prometheus metric, если endpoint отражает важное действие.
10. Добавь Loguru structured logs.
11. Добавь unit/component test.
12. Обнови OpenAPI contract, если endpoint публичный или internal cross-service.

## Типовая структура кода

```text
app/
  api/
    routes_<resource>.py
  schemas/
    <resource>.py
  services/
    <resource>_service.py
  repositories/
    <resource>_repository.py
  models/
    <resource>.py
```

## Route layer

Route layer должен:

- принимать HTTP request;
- валидировать input через Pydantic;
- вызывать service/use-case;
- возвращать response schema;
- не содержать бизнес-логику;
- не писать в БД напрямую.

Пример:

```python
from fastapi import APIRouter, Depends, status

from app.schemas.kitchen import KitchenCreate, KitchenRead
from app.services.kitchen_service import KitchenService, get_kitchen_service

router = APIRouter(prefix="/kitchens", tags=["kitchens"])


@router.post("", response_model=KitchenRead, status_code=status.HTTP_201_CREATED)
async def create_kitchen(
    payload: KitchenCreate,
    service: KitchenService = Depends(get_kitchen_service),
) -> KitchenRead:
    return await service.create_kitchen(payload)
```

## Service layer

Service layer должен:

- содержать бизнес-правила;
- вызывать repositories;
- вызывать внешние HTTP clients;
- публиковать domain/audit events;
- обновлять metrics;
- писать structured logs.

Пример:

```python
from loguru import logger


class KitchenService:
    def __init__(self, repository, event_publisher, metrics):
        self.repository = repository
        self.event_publisher = event_publisher
        self.metrics = metrics

    async def create_kitchen(self, payload):
        kitchen = await self.repository.create(payload)

        await self.event_publisher.publish(
            event_type="KitchenCreated",
            payload={"kitchen_id": str(kitchen.id)},
        )

        self.metrics.kitchens_created.inc()
        logger.info("kitchen_created", kitchen_id=str(kitchen.id))

        return kitchen
```

## Repository layer

Repository layer должен:

- работать с SQLAlchemy session;
- не знать про HTTP;
- не публиковать события;
- не менять чужие схемы БД.

## Тесты endpoint-а

Минимум:

- happy path;
- validation error;
- conflict/not found, если применимо;
- проверка побочного эффекта в БД;
- проверка события, если endpoint меняет бизнес-состояние.

## Definition of done

- endpoint работает;
- схема запроса/ответа описана;
- бизнес-логика не находится в route;
- добавлены tests;
- добавлены logs;
- добавлены metrics, если endpoint важный;
- добавлены Mongo events, если меняется бизнес-состояние;
- обновлен OpenAPI contract.

---

# Skill: добавить Mongo audit event

Используй этот skill, когда бизнес-событие должно сохраняться в MongoDB.

## Когда добавлять event

Добавляй event при изменении бизнес-состояния:

- order created;
- tasks created;
- task queued;
- task displayed;
- task claimed;
- task started;
- task completed;
- order ready_for_pickup;
- dispatch failed;
- capacity changed.

Не добавляй Mongo event для обычного debug/info application log.

## Структура event

```json
{
  "event_type": "TaskCompleted",
  "aggregate_type": "task",
  "aggregate_id": "task_123",
  "order_id": "order_123",
  "kitchen_id": "kitchen_123",
  "task_id": "task_123",
  "correlation_id": "...",
  "payload": {},
  "created_at": "2026-04-27T18:20:00Z"
}
```

## Правила

- Event пишется после успешного изменения состояния.
- Event не является источником текущего состояния.
- Текущее состояние хранится в PostgreSQL.
- Event должен быть idempotency-friendly, если операция идемпотентна.

---

# Skill: добавить метрику Prometheus

Используй этот skill, когда нужно наблюдать важное действие или состояние.

## Типы метрик

Counter:

- количество созданных заказов;
- количество queued/displayed/completed tasks;
- количество claim conflicts;
- количество retry/DLQ.

Gauge:

- visible backlog;
- busy slots;
- capacity;
- pending Redis messages.

Histogram:

- HTTP duration;
- dispatch latency;
- actual task duration.

## Правила labels

Хорошие labels:

- `service`
- `kitchen_id`
- `station_type`
- `station_id`
- `status`
- `reason`

Плохие labels:

- `order_id`
- `task_id`
- `request_id`
- произвольный exception message

Высококардинальные labels запрещены.

---

# Skill: написать integration test между сервисами

Используй этот skill, когда нужно проверить взаимодействие нескольких сервисов.

## Рекомендуемый подход

Для проекта допускаются два уровня:

1. Docker Compose integration tests.
2. Testcontainers-based tests.

Для учебного MVP проще начать с Docker Compose.

## Структура

```text
tests/
  integration/
    conftest.py
    test_fulfillment_menu_integration.py
    test_fulfillment_kitchen_integration.py
    test_worker_dispatch_integration.py
  e2e/
    test_order_to_ready_for_pickup.py
```

## Правила

- Не мокай сервис, если цель — проверить реальную интеграцию.
- Используй real PostgreSQL, Redis, MongoDB в контейнерах.
- Данные создавай через public/internal API, а не прямыми insert-ами, кроме seed инфраструктурных справочников.
- Для eventually consistent flows используй polling with timeout.
- Не используй `sleep` без условия. Используй `wait_until`.

## wait_until helper

```python
import asyncio
from collections.abc import Awaitable, Callable


async def wait_until(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout_seconds: float = 10.0,
    interval_seconds: float = 0.2,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_seconds

    while asyncio.get_event_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(interval_seconds)

    raise TimeoutError("Condition was not met in time")
```

## E2E business-flow test

Проверяем:

```text
1. create kitchen
2. create stations
3. create menu item
4. create recipe steps
5. set availability
6. create order
7. wait tasks queued
8. wait worker dispatch to KDS
9. claim task through KDS
10. complete task through KDS
11. wait order ready_for_pickup
12. assert Mongo events
13. assert metrics endpoints respond
```

Definition of done:

- test запускается одной командой;
- test не зависит от порядка запуска других тестов;
- test чистит данные или использует уникальные IDs;
- test проверяет не только HTTP 200, но и бизнес-состояние.
