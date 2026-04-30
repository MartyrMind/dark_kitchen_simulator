# Menu Service

Menu Service owns menu items, kitchen-specific menu availability, and ordered recipe steps for the dark kitchen system.

It does not create orders, kitchen tasks, KDS tasks, Redis messages, or Mongo audit events.

## Observability

`GET /metrics` exposes generic HTTP metrics:

```text
http_requests_total
http_request_duration_seconds
```

Menu Service does not write MongoDB business events in this MVP.

## Local Setup

```bash
cd services/menu-service
poetry install
```

Required environment variables:

```env
SERVICE_NAME=menu-service
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=readable
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/menu_service
```

For Docker use `DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/menu_service` and `LOG_FORMAT=json`.

## Database

```bash
poetry run alembic upgrade head
```

Alembic creates:

- `menu_items`
- `kitchen_menu_availability`
- `recipe_steps`

## Run

```bash
poetry run uvicorn app.main:app --reload
```

or:

```bash
poetry run python -m app.main --port 8000 --reload
```

## Tests

```bash
poetry run pytest
```

## API Examples

```bash
curl -X POST http://localhost:8000/menu-items \
  -H "Content-Type: application/json" \
  -d '{"name":"Burger","description":"Classic beef burger","status":"active"}'
```

```bash
curl http://localhost:8000/menu-items
```

```bash
curl -X POST http://localhost:8000/menu-items/{menu_item_id}/recipe-steps \
  -H "Content-Type: application/json" \
  -d '{"station_type":"grill","operation":"cook_patty","duration_seconds":480,"step_order":1}'
```

```bash
curl http://localhost:8000/menu-items/{menu_item_id}/recipe
```

```bash
curl -X POST http://localhost:8000/kitchens/{kitchen_id}/menu-items/{menu_item_id}/availability \
  -H "Content-Type: application/json" \
  -d '{"is_available":true}'
```

```bash
curl http://localhost:8000/kitchens/{kitchen_id}/menu
```
