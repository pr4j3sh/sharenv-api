from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.serialization import MongoDocument, SerializableDocument


class ProjectMember(SerializableDocument):
    user_id: str
    role: Literal["writer", "reader"]
    # Granted environment ids (explicit list). Owner is not stored here and has
    # implicit access to all environments.
    environments: list[str] = Field(default_factory=list)


class ProjectModel(MongoDocument):
    name: str
    user_id: str
    data_key: str
    key_version: int
    created_at: datetime
    updated_at: datetime
    members: list[ProjectMember] = Field(default_factory=list)
