from pydantic import BaseModel, field_validator

from app.core.validation import validate_project_env_name


class CreateEnvironmentReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_project_env_name(value, kind="Environment")


class CreateEnvironmentRes(BaseModel):
    environment_id: str


class DeleteEnvironmentRes(BaseModel):
    environment_id: str
