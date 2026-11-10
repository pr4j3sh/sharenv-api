import base64
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    DEBUG: bool = False
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    DATABASE: str = "sharenv_test"

    JWT_SECRET: str = ""
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_EXPIRY: int = 60

    ENCRYPTION_KEY: str = ""
    ENCRYPTION_KEY_VERSION: int = 1
    NONCE_SIZE: int = 12
    TOKEN_BYTES: int = 32
    KEY_INFO: str = "sharenv:project-key:v1"

    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Acme <onboarding@resend.dev>"

    OTP_EXPIRY: int = 10
    OTP_LENGTH: int = 6

    MIN_PASSWORD_LENGTH: int = 12
    MAX_PASSWORD_BYTES: int = 1024
    WEAK_PASSWORDS: set[str] = {
        "password123",
        "password1234",
        "qwerty123456",
        "123456789012",
        "admin123456",
        "letmein12345",
    }

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        secret = value.strip()

        if not secret:
            raise ValueError("JWT_SECRET must not be empty")

        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")

        if secret.lower() in {"secret", "password", "changeme"}:
            raise ValueError("JWT_SECRET is too weak")

        if len(set(secret)) < 8:
            raise ValueError("JWT_SECRET has insufficient character diversity")

        return secret

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        try:
            key = base64.b64decode(value, validate=True)
        except Exception as e:
            raise ValueError("ENCRYPTION_KEY must be valid base64") from e

        if len(key) != 32:
            raise ValueError("ENCRYPTION_KEY must decode to 32 bytes")

        return value

    @model_validator(mode="after")
    def validate_resend_api_key(self) -> "Settings":
        if not self.DEBUG and not self.RESEND_API_KEY.strip():
            raise ValueError("RESEND_API_KEY must not be empty when DEBUG is false")
        return self


settings = Settings()
