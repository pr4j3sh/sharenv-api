from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class VariableModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")
    name: str
    value_enc: str
    key_version: int
    environment_id: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
