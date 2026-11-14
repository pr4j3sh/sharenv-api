import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pwdlib import PasswordHash
from pydantic import PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_key_registry(raw: str) -> dict[int, bytes]:
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
    JWT_EXPIRY: int = 15

    REFRESH_TOKEN_EXPIRY_DAYS: int = 30

    ENCRYPTION_KEYS_JSON: str = ""
    ENCRYPTION_KEYS_FILE: str = ""
    ENCRYPTION_KEY_VERSION: int = 1
    NONCE_SIZE: int = 12
    TOKEN_BYTES: int = 32
    KEY_INFO: str = "sharenv:project-key:v1"

    EMAIL_PROVIDER: Literal["none", "console", "smtp", "resend"] = "none"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "sharenv <sharenv@localhost>"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: Literal["starttls", "ssl", "none"] = "starttls"
    SMTP_TIMEOUT: int = 10

    OTP_EXPIRY: int = 10
    OTP_LENGTH: int = 6

    MONGO_PING_TIMEOUT_SECONDS: float = 2.0

    AUTH_RATE_LIMIT_PER_IP: int = 30
    LOGIN_FAILURE_LIMIT: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    OTP_VERIFY_ATTEMPTS: int = 10
    OTP_RESEND_LIMIT: int = 3
    RATE_LIMIT_MAX_KEYS: int = 10_000

    INVITATION_EXPIRY_DAYS: int = 7

    DOCS_ENABLED: bool = False

    ALLOWED_HOSTS: str = "localhost,127.0.0.1,[::1],testserver"

    PAGINATION_DEFAULT_LIMIT: int = 50
    PAGINATION_MAX_LIMIT: int = 100

    JSON_MAX_DEPTH: int = 32
    JSON_MAX_NODES: int = 10000

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

    MAX_PROJECTS_PER_USER: int = 50
    MAX_ENVIRONMENTS_PER_PROJECT: int = 50
    MAX_VARIABLES_PER_ENVIRONMENT: int = 500
    MAX_TOTAL_VALUE_BYTES_PER_PROJECT: int = 5 * 1024 * 1024
    MAX_REQUEST_BODY_BYTES: int = 256 * 1024

    _encryption_keys: dict[int, bytes] = PrivateAttr(default_factory=dict)
    _master_ciphers: dict[int, AESGCM] = PrivateAttr(default_factory=dict)
    _dummy_otp_hash: str = PrivateAttr(default="")
    _dummy_password_hash: str = PrivateAttr(default="")

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
        return self._encryption_keys

    def master_cipher(self, key_version: int) -> AESGCM:
        if not self._master_ciphers:
            self._master_ciphers = {
                version: AESGCM(key) for version, key in self._encryption_keys.items()
            }
        cipher = self._master_ciphers.get(key_version)
        if cipher is None:
            raise ValueError(f"key version {key_version} is not in the key registry")
        return cipher

    def dummy_otp_hash(self) -> str:
        if not self._dummy_otp_hash:
            value = secrets.token_urlsafe(32)
            self._dummy_otp_hash = hmac.new(
                self.JWT_SECRET.encode(), value.encode(), hashlib.sha256
            ).hexdigest()
        return self._dummy_otp_hash

    def dummy_password_hash(self) -> str:
        if not self._dummy_password_hash:
            self._dummy_password_hash = PasswordHash.recommended().hash(
                secrets.token_urlsafe(32)
            )
        return self._dummy_password_hash

    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @model_validator(mode="after")
    def validate_email_provider(self) -> Settings:
        if self.EMAIL_PROVIDER == "console" and not self.DEBUG:
            raise ValueError(
                "EMAIL_PROVIDER=console logs OTP and invitation tokens;"
                " it is only allowed with DEBUG=true"
            )
        if (
            self.EMAIL_PROVIDER == "resend"
            and not self.DEBUG
            and not self.RESEND_API_KEY.strip()
        ):
            raise ValueError(
                "RESEND_API_KEY must not be empty when EMAIL_PROVIDER=resend"
            )
        if self.EMAIL_PROVIDER == "smtp":
            if not self.SMTP_HOST.strip():
                raise ValueError("SMTP_HOST must not be empty when EMAIL_PROVIDER=smtp")
            if not self.EMAIL_FROM.strip():
                raise ValueError(
                    "EMAIL_FROM must not be empty when EMAIL_PROVIDER=smtp"
                )
        return self

    @property
    def email_enabled(self) -> bool:
        return self.DEBUG or self.EMAIL_PROVIDER != "none"


settings = Settings()

NOT_AUTHENTICATED = {"WWW-Authenticate": "Bearer"}
