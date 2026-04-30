from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings


def create_mongo_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongo_url)
