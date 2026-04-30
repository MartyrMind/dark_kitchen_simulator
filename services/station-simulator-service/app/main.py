import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.core.config import get_settings
from app.metrics.metrics import get_default_metrics
from app.simulator.runner import SimulatorRunner
from dk_common.correlation import CorrelationIdMiddleware
from dk_common.health import build_health_response
from dk_common.logging import configure_logging
from dk_common.metrics import setup_metrics


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        service_name=settings.service_name,
        environment=settings.environment,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )
    metrics = get_default_metrics()
    runner = SimulatorRunner(settings, metrics)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await runner.start()
        try:
            yield
        finally:
            await runner.stop()

    app = FastAPI(title="Station Simulator Service", version=settings.version, lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    app.state.settings = settings
    app.state.metrics = metrics
    app.state.runner = runner

    @app.get("/health")
    async def health() -> dict[str, str | None]:
        return build_health_response(
            service_name=settings.service_name,
            environment=settings.environment,
            version=settings.version,
        )

    @app.get("/simulator/workers")
    async def simulator_workers() -> list[dict[str, str | int | None]]:
        return runner.worker_states()

    setup_metrics(app, service_name=settings.service_name)
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run station-simulator-service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
