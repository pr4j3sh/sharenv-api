from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProjectMember(BaseModel):
    user_id: str
    role: Literal["writer", "reader"]
    # Granted environment ids (explicit list). Owner is not stored here and has
    # implicit access to all environments.
    environments: list[str] = Field(default_factory=list)


class ProjectModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")
    name: str
    user_id: str
    data_key: str
    key_version: int
    created_at: datetime
    updated_at: datetime
    members: list[ProjectMember] = Field(default_factory=list)

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
