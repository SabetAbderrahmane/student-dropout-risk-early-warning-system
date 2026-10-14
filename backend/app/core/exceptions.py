from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _error_payload(
    code: str, message: str, details: Any | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "HTTP_ERROR"))
        message = str(exc.detail.get("message", "The request could not be completed."))
        details = exc.detail.get("details")
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
        details = None

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code, message, details),
        headers=exc.headers,
    )


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "VALIDATION_ERROR", "Request validation failed.", details
        ),
    )


async def application_exception_handler(
    _: Request, exc: ApplicationError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message, exc.details),
    )


async def database_conflict_handler(request, exc):
    # Account/password services roll back before reaching this boundary too.
    from app.services.casework_mutation import retryable_error

    conflict = retryable_error(exc)
    if conflict:
        return await application_exception_handler(request, conflict)
    return JSONResponse(
        status_code=500,
        content=_error_payload("DATABASE_ERROR", "The database request failed."),
    )
