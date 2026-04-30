# dk-common

Common infrastructure utilities for Dark Kitchen Python services.

This package is intentionally domain-free. It may contain logging setup, base settings, request correlation helpers, healthcheck helpers, and generic infrastructure exceptions.

It must not contain service SQLAlchemy models, repositories, use cases, order logic, kitchen logic, recipe logic, KDS logic, or clients that couple services through domain concepts.

## Install in a service

```toml
[tool.poetry.dependencies]
python = "^3.11"
dk-common = { path = "../../libs/python/dk_common", develop = true }
```

## Logging

```python
from dk_common.logging import configure_logging

configure_logging(
    service_name="example-service",
    environment="local",
    log_level="INFO",
    log_format="json",
)
```

## Correlation middleware

```python
from fastapi import FastAPI

from dk_common.correlation import CorrelationIdMiddleware

app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)
```

The middleware reads or generates `X-Correlation-ID` and `X-Request-ID`, stores them in request context, and returns them in response headers.

## Healthcheck

```python
from fastapi import FastAPI

from dk_common.health import build_health_response

app = FastAPI()


@app.get("/health")
async def health():
    return build_health_response(
        service_name="example-service",
        environment="local",
        version="0.1.0",
    )
```

`GET /health` returns:

```json
{
  "status": "ok",
  "service": "example-service",
  "environment": "local",
  "version": "0.1.0"
}
```

## Tests

```bash
cd libs/python/dk_common
poetry install
poetry run pytest
```
