from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.config import settings
from app.core.middleware import register_middlewares
from app.db.mongodb import mongo


def _sanitized_validation_detail(exc: RequestValidationError) -> list[dict[str, object]]:
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
                "loc": [str(part) for part in loc] if isinstance(loc, (list, tuple)) else [str(loc)],
                "msg": str(message),
                "type": str(error_type),
            }
        )
    return detail


@asynccontextmanager
async def startup(app: FastAPI):
    try:
        await mongo.connect()
        yield
    finally:
        await mongo.close()


# API docs are disabled unless DOCS_ENABLED is set, so production deployments
# do not expose /docs, /redoc, or /openapi.json by default.
app = FastAPI(
    title="sharenv API",
    lifespan=startup,
    **(
        {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}
        if settings.DOCS_ENABLED
        else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    ),
)

register_middlewares(app)
# CORS stays closed by default: no CORSMiddleware wildcard unless a browser
# client is introduced. TrustedHost narrows the accepted Host header(s).
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts() or ["localhost", "127.0.0.1", "[::1]", "testserver"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitized_validation_detail(exc)},
    )


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


app.include_router(router)
