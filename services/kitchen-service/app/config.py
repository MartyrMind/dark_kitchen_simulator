from pydantic import Field

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="kitchen-service", validation_alias="SERVICE_NAME")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/kitchen_service",
        validation_alias="DATABASE_URL",
    )
    mongo_url: str = Field(default="mongodb://localhost:27017", validation_alias="MONGO_URL")
    mongo_database: str = Field(default="dark_kitchen_events", validation_alias="MONGO_DATABASE")
    mongo_events_enabled: bool = Field(default=True, validation_alias="MONGO_EVENTS_ENABLED")


settings = Settings()
