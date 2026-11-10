from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router
from app.core.config import settings
from app.core.middleware import register_middlewares
from app.db.mongodb import mongo


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


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


app.include_router(router)
