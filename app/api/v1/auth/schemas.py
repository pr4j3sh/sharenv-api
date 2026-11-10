from pydantic import BaseModel, EmailStr, field_validator

from app.core.config import settings
from app.core.utils import validate_password_size


class RegisterReq(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_size(value)

        if len(value) < settings.MIN_PASSWORD_LENGTH:
            raise ValueError("Password must be at least 12 characters long")

        if value.strip().lower() in settings.WEAK_PASSWORDS:
            raise ValueError("Password is too weak")

        return value


class RegisterRes(BaseModel):
    success: bool
    user_id: str


class ResendOtpRes(BaseModel):
    success: bool
    user_id: str


class VerifyUserRes(BaseModel):
    token: str
    refresh_token: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class LoginRes(BaseModel):
    token: str
    refresh_token: str


class VerifyUserReq(BaseModel):
    otp: str


class RefreshReq(BaseModel):
    refresh_token: str


class RefreshRes(BaseModel):
    token: str
    refresh_token: str


class LogoutRes(BaseModel):
    success: bool


class EmailPayload(BaseModel):
    to: EmailStr
    subject: str = "Email Verification"
    otp: str
