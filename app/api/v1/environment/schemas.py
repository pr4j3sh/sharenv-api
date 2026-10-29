from pydantic import BaseModel


class CreateEnvironmentReq(BaseModel):
    name: str


class CreateEnvironmentRes(BaseModel):
    environment_id: str
