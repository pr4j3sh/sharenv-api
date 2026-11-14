from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health.routes import router as health_router
from app.api.v1.router import router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.middleware import register_middlewares
from app.db.mongodb import mongo


@asynccontextmanager
async def startup(app: FastAPI) -> AsyncIterator[None]:
    try:
        await mongo.connect()
        yield
    finally:
        await mongo.close()


app = FastAPI(
    title="sharenv API",
    lifespan=startup,
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)

register_middlewares(app)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(router)
