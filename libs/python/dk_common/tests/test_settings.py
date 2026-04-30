import pytest
from pydantic import ValidationError

from dk_common.settings import BaseServiceSettings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("SERVICE_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("VERSION", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)

    settings = BaseServiceSettings()

    assert settings.service_name == "dk-service"
    assert settings.environment == "local"
    assert settings.version == "0.1.0"
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "menu-service")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("VERSION", "1.2.3")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "readable")

    settings = BaseServiceSettings()

    assert settings.service_name == "menu-service"
    assert settings.environment == "test"
    assert settings.version == "1.2.3"
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "readable"


def test_settings_validates_log_format(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "plain")

    with pytest.raises(ValidationError):
        BaseServiceSettings()
