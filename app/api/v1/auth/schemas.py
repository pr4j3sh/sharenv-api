from pydantic import BaseModel


class RegisterReq(BaseModel):
    email: str
    password: str


class RegisterRes(BaseModel):
    token: str


class LoginReq(BaseModel):
    email: str
    password: str


class LoginRes(BaseModel):
    token: str
