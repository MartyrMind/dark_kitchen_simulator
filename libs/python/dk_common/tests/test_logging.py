import json

from loguru import logger

from dk_common.correlation import set_correlation_id, set_request_id
from dk_common.logging import configure_logging


def test_json_logging_includes_required_fields(capsys):
    set_correlation_id("corr-1")
    set_request_id("req-1")
    configure_logging("svc", "test", log_format="json")

    logger.info("hello")

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload["level"] == "INFO"
    assert payload["service"] == "svc"
    assert payload["environment"] == "test"
    assert payload["message"] == "hello"
    assert payload["correlation_id"] == "corr-1"
    assert payload["request_id"] == "req-1"


def test_readable_logging_writes_text(capsys):
    set_correlation_id("corr-2")
    set_request_id("req-2")
    configure_logging("svc", "local", log_format="readable")

    logger.info("hello")

    captured = capsys.readouterr()
    assert "svc" in captured.err
    assert "local" in captured.err
    assert "corr-2" in captured.err
    assert "req-2" in captured.err
    assert "hello" in captured.err


def test_configure_logging_replaces_handlers(capsys):
    configure_logging("svc", "test", log_format="json")
    configure_logging("svc", "test", log_format="json")

    logger.info("once")

    captured = capsys.readouterr()
    lines = [line for line in captured.err.splitlines() if line.strip()]
    assert len(lines) == 1
