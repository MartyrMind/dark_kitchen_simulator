from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


LogFormat = Literal["json", "readable"]


class BaseServiceSettings(BaseSettings):
    service_name: str = Field(default="dk-service", validation_alias="SERVICE_NAME")
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    version: str = Field(default="0.1.0", validation_alias="VERSION")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: LogFormat = Field(default="json", validation_alias="LOG_FORMAT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
