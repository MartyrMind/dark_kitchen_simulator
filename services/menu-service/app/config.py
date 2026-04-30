from pydantic import Field

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="menu-service", validation_alias="SERVICE_NAME")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/menu_service",
        validation_alias="DATABASE_URL",
    )


settings = Settings()
