import os
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SIMULATOR_ENABLED", "false")

from app.core.config import get_settings
from app.kds_client.schemas import KdsTask
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
def make_task():
    return _make_task


def _make_task(
    *,
    task_id: str = "task-1",
    status: str = "displayed",
    displayed_at: str = "2026-04-30T10:00:00Z",
    estimated_duration_seconds: int = 480,
) -> KdsTask:
    return KdsTask(
        kds_task_id=1,
        task_id=task_id,
        order_id="order-1",
        station_id=1,
        operation="cook_patty",
        menu_item_name="Burger",
        status=status,
        estimated_duration_seconds=estimated_duration_seconds,
        pickup_deadline=None,
        displayed_at=datetime.fromisoformat(displayed_at.replace("Z", "+00:00")).astimezone(timezone.utc),
    )
