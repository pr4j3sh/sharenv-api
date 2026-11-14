"""Sanitizers for error responses and the shared 422 handler."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def too_many_attempts(retry_after: int) -> HTTPException:
    """429 Too Many Requests with a Retry-After header."""
    return HTTPException(
        status_code=429,
        detail="Too many requests",
        headers={"Retry-After": str(retry_after)},
    )


def sanitized_validation_detail(exc: RequestValidationError) -> list[dict[str, object]]:
    """Return loc/msg/type only.

    FastAPI's default 422 response echoes the invalid `input` (and sometimes
    `ctx`), which can leak secret-bearing values. Keep just the safe parts.
    """

    detail: list[dict[str, object]] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        message = error.get("msg", "invalid value")
        error_type = error.get("type", "validation_error")
        detail.append(
            {
                "loc": [str(part) for part in loc]
                if isinstance(loc, (list, tuple))
                else [str(loc)],
                "msg": str(message),
                "type": str(error_type),
            }
        )
    return detail


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": sanitized_validation_detail(exc)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(RequestValidationError)(request_validation_exception_handler)
