from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class InvitationModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")
    project_id: str
    email: str
    role: str
    environments: list[str] = Field(default_factory=list)
    invited_by: str
    token_hash: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "expires_at", "accepted_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None
