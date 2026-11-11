from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings
from app.core.utils import validate_password_size
from app.core.validation import MAX_EMAIL_LENGTH, MAX_OTP_LENGTH, MAX_REFRESH_TOKEN_LENGTH


class RegisterReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
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
    # False when no mail provider is configured (EMAIL_PROVIDER=none):
    # the account is created unverified and verification is impossible.
    verification_required: bool = True


class ResendOtpReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)


class ResendOtpRes(BaseModel):
    success: bool


class VerifyUserRes(BaseModel):
    token: str
    refresh_token: str


class LoginReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_size(value)


class LoginRes(BaseModel):
    token: str
    refresh_token: str
    email_verified: bool


class VerifyUserReq(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    otp: str = Field(min_length=1, max_length=MAX_OTP_LENGTH)


class RefreshReq(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=MAX_REFRESH_TOKEN_LENGTH)


class RefreshRes(BaseModel):
    token: str
    refresh_token: str
    email_verified: bool


class LogoutRes(BaseModel):
    success: bool


class EmailPayload(BaseModel):
    to: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    subject: str = Field(default="Email Verification", max_length=200)
    otp: str = Field(min_length=1, max_length=MAX_OTP_LENGTH)
