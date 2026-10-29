from pydantic import BaseModel


class CreateProjectReq(BaseModel):
    name: str


class CreateProjectRes(BaseModel):
    project_id: str
