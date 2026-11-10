from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import validate_variable_name, validate_variable_value_size


class CreateVariableReq(BaseModel):
    name: str
    value: str | int | bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_variable_name(value)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | int | bool) -> str | int | bool:
        return validate_variable_value_size(value)


class CreateVariableRes(BaseModel):
    variable_id: str


class DeleteVariableRes(BaseModel):
    variable_id: str


class GetVariablesRes(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    value: str | int | bool | None
    environment_id: str
    created_at: datetime
    updated_at: datetime
    undecryptable: bool = False


class UpdateVariableReq(BaseModel):
    value: str | int | bool

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | int | bool) -> str | int | bool:
        return validate_variable_value_size(value)


class UpdateVariableRes(BaseModel):
    variable_id: str
