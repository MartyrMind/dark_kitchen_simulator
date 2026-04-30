class FulfillmentError(Exception):
    status_code = 500
    error = "internal_error"
    message = "Internal error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message


class NotFoundError(FulfillmentError):
    status_code = 404


class ConflictError(FulfillmentError):
    status_code = 409


class ExternalServiceUnavailableError(FulfillmentError):
    status_code = 503
