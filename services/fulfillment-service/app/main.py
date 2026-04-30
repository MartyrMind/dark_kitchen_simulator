import argparse

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.errors import install_error_handlers
from dk_common.correlation import CorrelationIdMiddleware
from dk_common.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(
        service_name=settings.service_name,
        environment=settings.environment,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )

    app = FastAPI(title="Fulfillment Service", version=settings.version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)
    install_error_handlers(app)
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fulfillment-service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
