from pydantic import BaseModel


class CreateVariableReq(BaseModel):
    name: str
    value: str | int | bool


class CreateVariableRes(BaseModel):
    variable_id: str
