from pymongo import AsyncMongoClient

from app.core.config import settings


class MongoClient:
    def __init__(self) -> None:
        if not settings.MONGO_URI or settings.MONGO_URI == "":
            raise Exception("MONGO_URI not found")

        self._uri: str = settings.MONGO_URI
        self.client: AsyncMongoClient = None
        self.db = None
        self.users = None
        self.projects = None
        self.environments = None
        self.variables = None

    async def connect(self, uri: str):
        try:
            if not uri:
                uri = self._uri

            self.client = AsyncMongoClient(uri)
            await self.client.admin.command("ping")
            self.client.get_database("sharenv_test")
            print("Connected successfully")

        except Exception as e:
            raise Exception("The following error occurred: ", e)
