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
from app.core.validation import validate_project_env_name


class CreateProjectReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_project_env_name(value, kind="Project")


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


class MemberRes(BaseModel):
    # Owner-only view of project membership. Email is resolved by joining the
    # users collection; unknown (deleted) accounts are reported with an empty
    # email rather than failing the whole list.
    user_id: str
    email: str
    role: Literal["owner", "writer", "reader"]
    environments: list[str] = Field(default_factory=list)


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

