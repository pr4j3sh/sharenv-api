from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.serialization import MongoDocument
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
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class DeleteProjectRes(BaseModel):
    project_id: str


class GetProjectsRes(MongoDocument):
    name: str
    user_id: str
    role: Literal["owner", "writer", "reader"]
    created_at: datetime
    updated_at: datetime


class MemberRes(BaseModel):
    user_id: str
    email: str
    role: Literal["owner", "writer", "reader"]
    environments: list[str] = Field(default_factory=list)


class UpdateMemberAccessReq(BaseModel):
    environments: list[str]
    role: Literal["writer", "reader"] | None = None
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
