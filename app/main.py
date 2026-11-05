from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.v1.router import router
from app.db.mongodb import mongo


@asynccontextmanager
async def startup(app: FastAPI):
    try:
        await mongo.connect()
        yield
    finally:
        await mongo.close()


app = FastAPI(title="sharenv API", lifespan=startup)


@app.middleware("http")
async def add_no_store_header(request: Request, call_next):
    response = await call_next(request)

    if request.url.path.startswith("/v1/variable"):
        response.headers["Cache-Control"] = "no-store"

    return response


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


app.include_router(router)
