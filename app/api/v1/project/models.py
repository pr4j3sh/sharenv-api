from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProjectModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")
    name: str
    user_id: str
    data_key: str
    created_at: datetime
    updated_at: datetime
    users: list[str] = []

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
