from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


def build_health_response(
    service_name: str,
    environment: str = "local",
    version: str | None = None,
) -> dict[str, str | None]:
    return {
        "status": "ok",
        "service": service_name,
        "environment": environment,
        "version": version,
    }


def create_health_router(
    service_name: str,
    environment: str = "local",
    version: str | None = None,
) -> APIRouter:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str | None]:
        return build_health_response(
            service_name=service_name,
            environment=environment,
            version=version,
        )

    return router
