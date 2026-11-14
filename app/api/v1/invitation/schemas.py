from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)

from app.core.serialization import MongoDocument, SerializableDocument
from app.core.utils import validate_password_size
from app.core.validation import MAX_EMAIL_LENGTH


class CreateInvitationReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    role: Literal["writer", "reader"]
    environments: list[str] = Field(default_factory=list)
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


class CreateInvitationRes(SerializableDocument):
    invitation_id: str
    project_id: str
    email: str
    role: Literal["writer", "reader"]
    environments: list[str]
    expires_at: datetime
    token: str
    email_sent: bool


class GetInvitationRes(MongoDocument):
    project_id: str
    email: str
    role: str
    environments: list[str] = Field(default_factory=list)
    invited_by: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None


class CancelInvitationReq(BaseModel):
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
