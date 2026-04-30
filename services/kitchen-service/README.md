# Kitchen Service

Kitchen Service owns kitchens, stations, station capacity and busy slot counters. This stage intentionally does not implement KDS endpoints or cross-service callbacks.

## Endpoints

- `GET /health`
- `POST /kitchens`
- `GET /kitchens`
- `GET /kitchens/{kitchen_id}`
- `POST /kitchens/{kitchen_id}/stations`
- `GET /kitchens/{kitchen_id}/stations`
- `GET /kitchens/{kitchen_id}/stations?station_type=grill`
- `PATCH /stations/{station_id}/capacity`
- `PATCH /stations/{station_id}/status`

## Environment

- `SERVICE_NAME`, default `kitchen-service`
- `ENVIRONMENT`, default `local`
- `VERSION`, default `0.1.0`
- `LOG_LEVEL`, default `INFO`
- `LOG_FORMAT`, default `json`
- `DATABASE_URL`, required, loaded from the environment or `.env`

## Local Development

```bash
cd services/kitchen-service
cp .env.example .env
poetry config virtualenvs.in-project true --local
poetry install
poetry run alembic upgrade head
poetry run python -m app.main --port 8001
poetry run pytest
```

Edit `.env` before running migrations or the service so `DATABASE_URL` points to your local PostgreSQL database.

The service connects to `dk-common` as a Poetry path dependency from `../../libs/python/dk_common`.
