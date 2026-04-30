from dk_common.errors import (
    ConfigurationError,
    DKCommonError,
    ExternalServiceError,
    HealthCheckError,
)


def test_common_error_to_dict_without_details():
    error = DKCommonError("Something failed")

    assert error.to_dict() == {
        "error": "dk_common_error",
        "message": "Something failed",
    }


def test_configuration_error_to_dict_with_details():
    error = ConfigurationError(
        "Invalid LOG_FORMAT",
        details={"allowed": ["json", "readable"]},
    )

    assert error.to_dict() == {
        "error": "configuration_error",
        "message": "Invalid LOG_FORMAT",
        "details": {"allowed": ["json", "readable"]},
    }


def test_external_service_error_to_dict():
    assert ExternalServiceError("HTTP failed").to_dict()["error"] == "external_service_error"


def test_health_check_error_to_dict():
    assert HealthCheckError("Not healthy").to_dict()["error"] == "health_check_error"
