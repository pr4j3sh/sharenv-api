from pydantic import BaseModel, EmailStr


class RegisterReq(BaseModel):
    email: EmailStr
    password: str


class RegisterRes(BaseModel):
    success: bool
    user_id: str


class ResendOtpRes(BaseModel):
    success: bool
    user_id: str


class VerifyUserRes(BaseModel):
    token: str


class LoginReq(BaseModel):
    email: str
    password: str


class LoginRes(BaseModel):
    token: str


class EmailPayload(BaseModel):
    to: EmailStr
    subject: str = "Email Verification"
    otp: str
