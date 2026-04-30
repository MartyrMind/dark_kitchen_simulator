from pydantic import Field

from dk_common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="kitchen-service", validation_alias="SERVICE_NAME")
    database_url: str = Field(validation_alias="DATABASE_URL")


settings = Settings()
