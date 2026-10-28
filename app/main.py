from contextlib import asynccontextmanager

from fastapi import FastAPI

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

app.include_router(router)
