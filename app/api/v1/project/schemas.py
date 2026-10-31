import re

from pydantic import BaseModel, field_validator


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
    email: str


class AddUserRes(BaseModel):
    project_id: str
