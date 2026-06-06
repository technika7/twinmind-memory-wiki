"""
RFC 7807 Problem Details error handlers.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Resource not found."""
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found")


class ConflictError(Exception):
    """Resource conflict (e.g., duplicate processing)."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the app."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "type": "https://memorywiki.dev/errors/not-found",
                "title": f"{exc.resource} Not Found",
                "status": 404,
                "detail": str(exc),
                "instance": str(request.url),
            },
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        return JSONResponse(
            status_code=409,
            content={
                "type": "https://memorywiki.dev/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": exc.detail,
                "instance": str(request.url),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://memorywiki.dev/errors/validation",
                "title": "Validation Error",
                "status": 422,
                "detail": "The request body contains invalid data.",
                "errors": exc.errors(),
                "instance": str(request.url),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://memorywiki.dev/errors/internal",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred. Please try again later.",
                "instance": str(request.url),
            },
        )
