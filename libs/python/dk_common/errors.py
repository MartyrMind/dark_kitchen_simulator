from __future__ import annotations

from typing import Any


class DKCommonError(Exception):
    code = "dk_common_error"

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ConfigurationError(DKCommonError):
    code = "configuration_error"


class ExternalServiceError(DKCommonError):
    code = "external_service_error"


class HealthCheckError(DKCommonError):
    code = "health_check_error"
