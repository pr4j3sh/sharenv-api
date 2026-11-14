from datetime import datetime

from app.core.serialization import MongoDocument


class EnvironmentModel(MongoDocument):
    name: str
    project_id: str
    created_at: datetime
    updated_at: datetime
