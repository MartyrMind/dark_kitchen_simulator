from pydantic import Field

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="fulfillment-service", validation_alias="SERVICE_NAME")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment_service",
        validation_alias="DATABASE_URL",
    )
    kitchen_service_url: str = Field(default="http://localhost:8001", validation_alias="KITCHEN_SERVICE_URL")
    menu_service_url: str = Field(default="http://localhost:8002", validation_alias="MENU_SERVICE_URL")
    http_timeout_seconds: float = Field(default=3.0, validation_alias="HTTP_TIMEOUT_SECONDS")
    enable_redis_publishing: bool = Field(default=False, validation_alias="ENABLE_REDIS_PUBLISHING")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    redis_task_stream_prefix: str = Field(default="stream:kitchen", validation_alias="REDIS_TASK_STREAM_PREFIX")
    redis_publish_enabled: bool = Field(default=True, validation_alias="REDIS_PUBLISH_ENABLED")
    mongo_url: str = Field(default="mongodb://localhost:27017", validation_alias="MONGO_URL")
    mongo_database: str = Field(default="dark_kitchen_events", validation_alias="MONGO_DATABASE")
    mongo_events_enabled: bool = Field(default=True, validation_alias="MONGO_EVENTS_ENABLED")


settings = Settings()
