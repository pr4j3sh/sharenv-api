import base64

from pydantic import field_validator
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
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY: int = 60

    ENCRYPTION_KEY: str = ""
    ENCRYPTION_KEY_VERSION: int = 1
    NONCE_SIZE: int = 12
    TOKEN_BYTES: int = 32
    KEY_INFO: str = "sharenv:project-key:v1"

    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Acme <onboarding@resend.dev>"

    OTP_EXPIRY: int = 1
    OTP_LENGTH: int = 6

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JWT_SECRET must not be empty")
        return value

    @field_validator("RESEND_API_KEY")
    @classmethod
    def validate_resend_api_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("RESEND_API_KEY must not be empty")
        return value

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


settings = Settings()
