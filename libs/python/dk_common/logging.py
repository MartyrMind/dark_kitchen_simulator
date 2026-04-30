from __future__ import annotations

if __name__ == "logging":
    import importlib.util
    import sys
    import sysconfig
    from pathlib import Path

    stdlib_logging = Path(sysconfig.get_path("stdlib")) / "logging" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "logging",
        stdlib_logging,
        submodule_search_locations=[str(stdlib_logging.parent)],
    )
    if spec is None or spec.loader is None:
        msg = "Could not load stdlib logging module"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules["logging"] = module
    spec.loader.exec_module(module)
    globals().update(module.__dict__)
else:
    import json
    import sys
    from datetime import timezone
    from typing import Any, Literal

    from loguru import logger

    from dk_common.correlation import get_correlation_id, get_request_id

    LogFormat = Literal["json", "readable"]

    def _json_sink(message) -> None:
        record = message.record
        payload: dict[str, Any] = {
            "timestamp": record["time"].astimezone(timezone.utc).isoformat(),
            "level": record["level"].name,
            "service": record["extra"].get("service"),
            "environment": record["extra"].get("environment"),
            "message": record["message"],
            "correlation_id": record["extra"].get("correlation_id"),
            "request_id": record["extra"].get("request_id"),
        }

        for key in ("order_id", "task_id", "station_id", "event"):
            if key in record["extra"]:
                payload[key] = record["extra"][key]

        sys.stderr.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")

    def configure_logging(
        service_name: str,
        environment: str,
        log_level: str = "INFO",
        log_format: LogFormat = "json",
    ) -> None:
        if log_format not in ("json", "readable"):
            msg = "log_format must be either 'json' or 'readable'"
            raise ValueError(msg)

        def add_context(record: dict[str, Any]) -> None:
            record["extra"].setdefault("service", service_name)
            record["extra"].setdefault("environment", environment)
            record["extra"]["correlation_id"] = get_correlation_id()
            record["extra"]["request_id"] = get_request_id()

        logger.remove()
        logger.configure(patcher=add_context)

        if log_format == "json":
            logger.add(_json_sink, level=log_level, enqueue=False)
            return

        logger.add(
            sys.stderr,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</green> "
                "| <level>{level}</level> "
                "| {extra[service]} "
                "| {extra[environment]} "
                "| correlation_id={extra[correlation_id]} "
                "| request_id={extra[request_id]} "
                "| <level>{message}</level>"
            ),
            enqueue=False,
        )

    __all__ = ["configure_logging", "logger"]
