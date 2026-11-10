from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.core.utils import validate_password_size
from app.core.validation import MAX_EMAIL_LENGTH


class CreateInvitationReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    role: Literal["writer", "reader"]
    # Granted environment ids (must belong to the project; may be empty).
    environments: list[str] = Field(default_factory=list)
    # Owner re-authentication.
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("environments")
    @classmethod
    def validate_environments(cls, value: list[str]) -> list[str]:
        if len(value) > 200:
            raise ValueError("too many environments")
        for env_id in value:
            if not isinstance(env_id, str) or len(env_id) != 24:
                raise ValueError("invalid environment id")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class CreateInvitationRes(BaseModel):
    invitation_id: str
    project_id: str
    email: str
    role: Literal["writer", "reader"]
    environments: list[str]
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class GetInvitationRes(BaseModel):
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
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "expires_at", "accepted_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class CancelInvitationReq(BaseModel):
    # Owner re-authentication.
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class CancelInvitationRes(BaseModel):
    invitation_id: str


class AcceptInvitationRes(BaseModel):
    project_id: str
    role: Literal["writer", "reader"]
    environments: list[str]
