import os
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from app.api.routes import get_kitchen_client, get_menu_client, get_task_event_writer, get_task_publisher
from app.db import Base, get_session
from app.main import create_app
from app.schemas import KitchenMenuItemSnapshot, KitchenSnapshot, RecipeSnapshot, RecipeStepSnapshot


BURGER_ID = UUID("3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce")
FRIES_ID = UUID("c98f500a-647c-42f1-85a4-07ef114a84ad")
KITCHEN_ID = UUID("d53b7d88-b23c-4bb8-a403-6238c810092a")


class FakeKitchenClient:
    def __init__(self, status: str = "active", exists: bool = True) -> None:
        self.status = status
        self.exists = exists
        self.calls = 0

    async def get_kitchen(self, kitchen_id):
        from app.clients.kitchen import KitchenNotActiveError, KitchenNotFoundError

        self.calls += 1
        if not self.exists:
            raise KitchenNotFoundError()
        if self.status != "active":
            raise KitchenNotActiveError()
        return KitchenSnapshot(id=kitchen_id, status=self.status)


class FakeMenuClient:
    def __init__(self, available: bool = True, empty_recipe: bool = False) -> None:
        self.available = available
        self.empty_recipe = empty_recipe
        self.menu_calls = 0
        self.recipe_calls = 0

    async def get_kitchen_menu(self, kitchen_id):
        self.menu_calls += 1
        return [
            KitchenMenuItemSnapshot(id=BURGER_ID, name="Burger", status="active", is_available=self.available),
            KitchenMenuItemSnapshot(id=FRIES_ID, name="Fries", status="active", is_available=False),
        ]

    async def get_recipe(self, menu_item_id):
        self.recipe_calls += 1
        steps = [] if self.empty_recipe else [
            RecipeStepSnapshot(
                station_type="packaging",
                operation="pack_burger",
                duration_seconds=60,
                step_order=2,
            ),
            RecipeStepSnapshot(
                station_type="grill",
                operation="cook_patty",
                duration_seconds=480,
                step_order=1,
            ),
        ]
        return RecipeSnapshot(menu_item_id=menu_item_id, steps=steps)


class FakeTaskPublisher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.published = []

    async def publish_task(self, task, order, menu_item_name):
        from app.domain.errors import TaskPublishFailedError
        from app.redis.streams import build_task_stream_name

        if self.fail:
            raise TaskPublishFailedError()
        stream = build_task_stream_name(order.kitchen_id, task.station_type)
        redis_message_id = f"fake-{len(self.published)}-0"
        self.published.append(
            {
                "task_id": task.id,
                "order_id": order.id,
                "stream": stream,
                "redis_message_id": redis_message_id,
                "menu_item_name": menu_item_name,
            }
        )
        return stream, redis_message_id


class FakeTaskEventWriter:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    async def write_task_queued(self, task, order, stream, redis_message_id):
        if self.fail:
            raise RuntimeError("mongo failed")
        self.events.append(
            {
                "event_type": "TaskQueued",
                "task_id": str(task.id),
                "order_id": str(order.id),
                "kitchen_id": str(order.kitchen_id),
                "station_type": task.station_type,
                "payload": {"stream": stream, "redis_message_id": redis_message_id},
            }
        )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db_session:
        yield db_session

    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with SessionLocal() as db_session:
            yield db_session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_kitchen_client] = lambda: FakeKitchenClient()
    app.dependency_overrides[get_menu_client] = lambda: FakeMenuClient()
    app.dependency_overrides[get_task_publisher] = lambda: FakeTaskPublisher()
    app.dependency_overrides[get_task_event_writer] = lambda: FakeTaskEventWriter()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client

    await engine.dispose()


@pytest.fixture
def order_payload():
    return {
        "kitchen_id": str(KITCHEN_ID),
        "items": [{"menu_item_id": str(BURGER_ID), "quantity": 2}],
    }
