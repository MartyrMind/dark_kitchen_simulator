from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services import ConflictError, NotFoundError

ERROR_MESSAGES = {
    "menu_item_not_found": "Menu item not found",
    "menu_item_already_exists": "Menu item with this name already exists",
    "recipe_step_order_already_exists": "Recipe step with this step_order already exists for menu item",
}


def _error_response(status_code: int, error: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "details": details or {}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        error = str(exc)
        return _error_response(404, error, ERROR_MESSAGES.get(error, "Resource not found"))

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
        error = str(exc)
        return _error_response(409, error, ERROR_MESSAGES.get(error, "Conflict"))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(422, "validation_error", "Request validation failed", {"errors": exc.errors()})
