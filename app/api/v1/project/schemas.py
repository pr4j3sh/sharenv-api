import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


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


class AddUserReq(BaseModel):
    email: EmailStr


class AddUserRes(BaseModel):
    project_id: str


class DeleteProjectRes(BaseModel):
    project_id: str


class GetProjectsRes(BaseModel):
    id: str = Field(alias="_id")
    name: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
