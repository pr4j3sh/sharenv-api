from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateVariableReq(BaseModel):
    name: str
    value: str | int | bool


class CreateVariableRes(BaseModel):
    variable_id: str


class DeleteVariableRes(BaseModel):
    variable_id: str


class GetVariablesRes(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    value: str | int | bool
    environment_id: str
    created_at: datetime
    updated_at: datetime


class UpdateVariableReq(BaseModel):
    value: str


class UpdateVariableRes(BaseModel):
    variable_id: str
