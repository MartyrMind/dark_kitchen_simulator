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


settings = Settings()
