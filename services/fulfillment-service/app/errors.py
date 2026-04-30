from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import FulfillmentError


def error_response(status_code: int, error: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "details": details or {}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FulfillmentError)
    async def fulfillment_error_handler(_: Request, exc: FulfillmentError) -> JSONResponse:
        return error_response(exc.status_code, exc.error, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "validation_error", "Request validation failed", {"errors": exc.errors()})
