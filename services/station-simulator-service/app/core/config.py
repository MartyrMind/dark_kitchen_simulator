from functools import lru_cache

from dk_common.settings import BaseServiceSettings
from pydantic import Field, field_validator


class Settings(BaseServiceSettings):
    service_name: str = Field(default="station-simulator-service", validation_alias="SERVICE_NAME")

    kitchen_service_url: str = Field(default="http://localhost:8001", validation_alias="KITCHEN_SERVICE_URL")
    http_timeout_seconds: float = Field(default=3.0, validation_alias="HTTP_TIMEOUT_SECONDS")

    simulator_enabled: bool = Field(default=True, validation_alias="SIMULATOR_ENABLED")
    simulator_speed_factor: float = Field(default=60.0, validation_alias="SIMULATOR_SPEED_FACTOR")
    simulator_poll_interval_ms: int = Field(default=1000, validation_alias="SIMULATOR_POLL_INTERVAL_MS")
    simulator_workers_config: str = Field(
        default="grill_1:2,fryer_1:1,packaging_1:1",
        validation_alias="SIMULATOR_WORKERS_CONFIG",
    )
    simulator_min_duration_factor: float = Field(default=0.7, validation_alias="SIMULATOR_MIN_DURATION_FACTOR")
    simulator_max_duration_factor: float = Field(default=1.4, validation_alias="SIMULATOR_MAX_DURATION_FACTOR")

    @field_validator("kitchen_service_url")
    @classmethod
    def validate_kitchen_service_url(cls, value: str) -> str:
        if not value.strip():
            msg = "kitchen_service_url must not be empty"
            raise ValueError(msg)
        return value.rstrip("/")

    @field_validator("http_timeout_seconds", "simulator_speed_factor")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "value must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("simulator_poll_interval_ms")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            msg = "simulator_poll_interval_ms must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("simulator_min_duration_factor")
    @classmethod
    def validate_min_duration_factor(cls, value: float) -> float:
        if value <= 0:
            msg = "simulator_min_duration_factor must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("simulator_max_duration_factor")
    @classmethod
    def validate_duration_factors(cls, value: float, info) -> float:
        min_factor = info.data.get("simulator_min_duration_factor")
        if min_factor is not None and min_factor <= 0:
            msg = "simulator_min_duration_factor must be greater than 0"
            raise ValueError(msg)
        if value <= 0:
            msg = "simulator_max_duration_factor must be greater than 0"
            raise ValueError(msg)
        if min_factor is not None and value < min_factor:
            msg = "simulator_max_duration_factor must be greater than or equal to simulator_min_duration_factor"
            raise ValueError(msg)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
