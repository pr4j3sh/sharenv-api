from pydantic import BaseModel
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.core.logger import get_logger

log = get_logger(__name__)


class MongoConnectPayload(BaseModel):
    uri: str | None = None
    database: str | None = None


class MongoClient:
    def __init__(self) -> None:
        if not settings.MONGO_URI:
            raise ValueError("MONGO_URI cannot be empty")

        if not settings.DATABASE:
            raise ValueError("DATABASE cannot be empty")

        self._uri: str = settings.MONGO_URI
        self._database: str = settings.DATABASE

        self.client: AsyncMongoClient | None = None
        self.db: AsyncDatabase | None = None
        self.users: AsyncCollection | None = None
        self.projects: AsyncCollection | None = None
        self.environments: AsyncCollection | None = None
        self.variables: AsyncCollection | None = None

    async def connect(self, payload: MongoConnectPayload | None = None) -> None:
        uri = payload.uri if payload and payload.uri else self._uri
        database = payload.database if payload and payload.database else self._database

        try:
            self.client = AsyncMongoClient(uri)

            await self.client.admin.command("ping")

            self.db = self.client.get_database(database)

            self.users = self.db["users"]
            self.projects = self.db["projects"]
            self.environments = self.db["environments"]
            self.variables = self.db["variables"]

            log.info(f"connected to mongodb {database} successfully")

        except Exception as e:
            log.error(e)
            await self.close()
            raise

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()

        self.client = None
        self.db = None
        self.users = None
        self.projects = None
        self.environments = None
        self.variables = None


mongo = MongoClient()
