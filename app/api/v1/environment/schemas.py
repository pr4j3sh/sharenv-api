import re

from pydantic import BaseModel, field_validator


class CreateEnvironmentReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9_-]+", value):
            raise ValueError(
                "Environment name must contain only lowercase letters, numbers, hyphens, and underscores."
            )
        return value


class CreateEnvironmentRes(BaseModel):
    environment_id: str
