class FulfillmentError(Exception):
    status_code = 500
    error = "internal_error"
    message = "Internal error"

    details: dict = {}

    def __init__(self, message: str | None = None, details: dict | None = None) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.details = details or {}


class NotFoundError(FulfillmentError):
    status_code = 404


class ConflictError(FulfillmentError):
    status_code = 409


class ExternalServiceUnavailableError(FulfillmentError):
    status_code = 503


class RedisUnavailableError(ExternalServiceUnavailableError):
    error = "redis_unavailable"
    message = "Redis is unavailable"


class TaskPublishFailedError(ExternalServiceUnavailableError):
    error = "task_publish_failed"
    message = "Task publish failed"
