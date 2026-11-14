"""Shared pydantic serializers for stored documents and document-shaped schemas.

Mongo documents use ``_id``/:class:`ObjectId` and datetimes; API responses expose
plain string ids and ISO-8601 datetimes instead. Subclassing the bases below
removes the per-model copy-pasted field serializers.
"""

from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SerializableDocument(BaseModel):
    """Base model that serializes known datetime fields to ISO-8601 strings."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer("created_at", "updated_at", "expires_at", check_fields=False)
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("accepted_at", "otp_expiry", check_fields=False)
    def serialize_optional_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class MongoDocument(SerializableDocument):
    """Base model for documents stored in MongoDB with an ``ObjectId`` primary key."""

    id: ObjectId | None = Field(default=None, alias="_id")

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None
