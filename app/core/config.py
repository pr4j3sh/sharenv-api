import base64
import json
from pathlib import Path
from typing import Literal

from pydantic import PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_key_registry(raw: str) -> dict[int, bytes]:
    """Parse a {"<version>": "<base64 32-byte key>"} master key registry."""
    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("key registry must be a valid JSON object") from e

    if not isinstance(registry, dict) or not registry:
        raise ValueError("key registry must be a non-empty JSON object")

    parsed: dict[int, bytes] = {}

    for version, key in registry.items():
        if not isinstance(version, str) or not version.isdigit():
            raise ValueError(
                f"key registry version {version!r} must be an integer string"
            )

        if not isinstance(key, str):
            raise TypeError(
                f"key registry entry for version {version} must be a base64 string"
            )

        try:
            decoded = base64.b64decode(key, validate=True)
        except Exception as e:
            raise ValueError(
                f"key registry entry for version {version} must be valid base64"
            ) from e

        if len(decoded) != 32:
            raise ValueError(
                f"key registry entry for version {version} must decode to 32 bytes"
            )

        if int(version) in parsed:
            raise ValueError(f"key registry has duplicate version {version}")

        parsed[int(version)] = decoded

    return parsed


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

    # Master key registry: either inline JSON ({"<version>": "<base64 key>"})
    # or a path to a file containing the same JSON (e.g. a Docker secret).
    # ENCRYPTION_KEY_VERSION is the active version used for new writes.
    ENCRYPTION_KEYS_JSON: str = ""
    ENCRYPTION_KEYS_FILE: str = ""
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

    _encryption_keys: dict[int, bytes] = PrivateAttr(default_factory=dict)

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

    @model_validator(mode="after")
    def validate_encryption_keys(self) -> Settings:
        if self.ENCRYPTION_KEYS_JSON and self.ENCRYPTION_KEYS_FILE:
            raise ValueError(
                "set only one of ENCRYPTION_KEYS_JSON and ENCRYPTION_KEYS_FILE"
            )

        if not self.ENCRYPTION_KEYS_JSON and not self.ENCRYPTION_KEYS_FILE:
            raise ValueError("ENCRYPTION_KEYS_JSON or ENCRYPTION_KEYS_FILE must be set")

        if self.ENCRYPTION_KEYS_FILE:
            try:
                raw = Path(self.ENCRYPTION_KEYS_FILE).read_text(encoding="utf-8")
            except OSError as e:
                raise ValueError(
                    f"cannot read ENCRYPTION_KEYS_FILE {self.ENCRYPTION_KEYS_FILE}"
                ) from e
        else:
            raw = self.ENCRYPTION_KEYS_JSON

        keys = _parse_key_registry(raw)

        if self.ENCRYPTION_KEY_VERSION not in keys:
            raise ValueError(
                f"ENCRYPTION_KEY_VERSION {self.ENCRYPTION_KEY_VERSION} is missing"
                " from the key registry"
            )

        self._encryption_keys = keys
        return self

    def encryption_keys(self) -> dict[int, bytes]:
        """Configured master keys by version; the active version is
        ENCRYPTION_KEY_VERSION."""
        return self._encryption_keys

    @model_validator(mode="after")
    def validate_resend_api_key(self) -> Settings:
        if not self.DEBUG and not self.RESEND_API_KEY.strip():
            raise ValueError("RESEND_API_KEY must not be empty when DEBUG is false")
        return self


settings = Settings()
