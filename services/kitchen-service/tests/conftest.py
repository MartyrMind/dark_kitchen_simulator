import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from app.db import Base, get_session
from app.main import create_app
from app.clients import get_fulfillment_client


class FakeFulfillmentClient:
    def __init__(self):
        self.start_calls = []
        self.complete_calls = []
        self.fail_start = False
        self.fail_complete = False

    async def start_task(self, task_id, **payload):
        if self.fail_start:
            from app.clients import FulfillmentClientError

            raise FulfillmentClientError("fulfillment_service_unavailable")
        self.start_calls.append((task_id, payload))

    async def complete_task(self, task_id, **payload):
        if self.fail_complete:
            from app.clients import FulfillmentClientError

            raise FulfillmentClientError("fulfillment_service_unavailable")
        self.complete_calls.append((task_id, payload))


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
        async with SessionLocal() as session:
            yield session

    app = create_app()
    fake_fulfillment_client = FakeFulfillmentClient()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_fulfillment_client] = lambda: fake_fulfillment_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        http_client.fulfillment_client = fake_fulfillment_client
        yield http_client

    await engine.dispose()
