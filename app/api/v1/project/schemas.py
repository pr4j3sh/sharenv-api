import re
from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from app.core.utils import validate_password_size


class CreateProjectReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9_-]+", value):
            raise ValueError(
                "Project name must contain only lowercase letters, numbers, hyphens, and underscores."
            )
        return value


class CreateProjectRes(BaseModel):
    project_id: str


class DeleteProjectReq(BaseModel):
    # The caller's current password; deleting a project re-authenticates.
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class DeleteProjectRes(BaseModel):
    project_id: str


class GetProjectsRes(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")
    name: str
    user_id: str
    role: Literal["owner", "writer", "reader"]
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: ObjectId | None) -> str | None:
        return str(value) if value else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class UpdateMemberAccessReq(BaseModel):
    # Full replacement of the member's granted environment ids (add/remove by
    # inclusion). Each id must belong to the project.
    environments: list[str]
    # Optionally adjust the member's role in the same request.
    role: Literal["writer", "reader"] | None = None
    # Owner re-authentication.
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class UpdateMemberAccessRes(BaseModel):
    project_id: str
    user_id: str
    role: Literal["writer", "reader"]
    environments: list[str]


class RemoveMemberReq(BaseModel):
    # Owner re-authentication (required for removing another member).
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class RemoveMemberRes(BaseModel):
    project_id: str
    user_id: str


class LeaveProjectRes(BaseModel):
    project_id: str
    user_id: str

