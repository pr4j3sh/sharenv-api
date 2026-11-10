from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings


async def limit_request_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413, content={"detail": "Request body too large"}
                )
        except ValueError:
            return JSONResponse(
                status_code=400, content={"detail": "Invalid Content-Length header"}
            )
    return await call_next(request)


async def add_no_store_header(request: Request, call_next):
    response = await call_next(request)

    if request.url.path.startswith("/v1/variable"):
        response.headers["Cache-Control"] = "no-store"

    return response


def register_middlewares(app: FastAPI) -> None:
    # Registered in order: body-size guard runs before routing/handlers.
    app.middleware("http")(limit_request_body_size)
    app.middleware("http")(add_no_store_header)
