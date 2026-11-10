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
    JWT_EXPIRY: int = 15

    REFRESH_TOKEN_EXPIRY_DAYS: int = 30

    # Master key registry: either inline JSON ({"<version>": "<base64 key>"})
    # or a path to a file containing the same JSON (e.g. a Docker secret).
    # ENCRYPTION_KEY_VERSION is the active version used for new writes.
    ENCRYPTION_KEYS_JSON: str = ""
    ENCRYPTION_KEYS_FILE: str = ""
    ENCRYPTION_KEY_VERSION: int = 1
    NONCE_SIZE: int = 12
    TOKEN_BYTES: int = 32
    KEY_INFO: str = "sharenv:project-key:v1"

    # Email provider:
    #   none    — default. No mail is sent; accounts stay unverified and
    #             unverified users may log in. Invites are shared out-of-band
    #             via the token returned by the invitation endpoint.
    #   console — log delivery (dev only; never enable DEBUG in production)
    #   smtp    — generic SMTP relay (org mail infra, Workspace, M365, SES…)
    #   resend  — Resend API (requires RESEND_API_KEY)
    EMAIL_PROVIDER: Literal["none", "console", "smtp", "resend"] = "none"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "sharenv <sharenv@localhost>"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: Literal["starttls", "ssl", "none"] = "starttls"
    SMTP_TIMEOUT: int = 10  # seconds

    OTP_EXPIRY: int = 10
    OTP_LENGTH: int = 6

    # Auth rate limiting. The app-level counters are in-memory and
    # single-process only; nginx adds a coarse outer limit (deploy/nginx/).
    AUTH_RATE_LIMIT_PER_IP: int = 30  # requests per minute across /v1/auth/*
    LOGIN_FAILURE_LIMIT: int = 5  # failed logins per email before lockout
    LOGIN_LOCKOUT_MINUTES: int = 15
    OTP_VERIFY_ATTEMPTS: int = 10  # wrong OTP guesses per user per OTP lifetime
    OTP_RESEND_LIMIT: int = 3  # OTP resends per user per OTP lifetime

    INVITATION_EXPIRY_DAYS: int = 7

    # API docs (/docs, /redoc, /openapi.json); disabled by default.
    DOCS_ENABLED: bool = False

    # Explicit Host allowlist for TrustedHostMiddleware. Comma-separated.
    # Set to the public hostname(s) in production (e.g. "sharenv.example.com").
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,[::1],testserver"

    # Pagination for list endpoints. Responses remain JSON lists; totals and
    # the next offset are exposed via X-Total-Count/X-Limit/X-Offset/X-Next-Offset.
    PAGINATION_DEFAULT_LIMIT: int = 50
    PAGINATION_MAX_LIMIT: int = 100

    # Guard for JSON request bodies in addition to the byte limit.
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

    # Input validation quotas (DB is treated as temporary; counts are best-effort
    # under concurrency without transactional counters).
    MAX_PROJECTS_PER_USER: int = 50
    MAX_ENVIRONMENTS_PER_PROJECT: int = 50
    MAX_VARIABLES_PER_ENVIRONMENT: int = 500
    MAX_TOTAL_VALUE_BYTES_PER_PROJECT: int = 5 * 1024 * 1024
    MAX_REQUEST_BODY_BYTES: int = 256 * 1024

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

    def allowed_hosts(self) -> list[str]:
        """Parsed explicit host allowlist for TrustedHostMiddleware."""
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @model_validator(mode="after")
    def validate_email_provider(self) -> Settings:
        if self.EMAIL_PROVIDER == "resend" and not self.DEBUG:
            if not self.RESEND_API_KEY.strip():
                raise ValueError("RESEND_API_KEY must not be empty when EMAIL_PROVIDER=resend")
        if self.EMAIL_PROVIDER == "smtp":
            if not self.SMTP_HOST.strip():
                raise ValueError("SMTP_HOST must not be empty when EMAIL_PROVIDER=smtp")
            if not self.EMAIL_FROM.strip():
                raise ValueError("EMAIL_FROM must not be empty when EMAIL_PROVIDER=smtp")
        return self

    @property
    def email_enabled(self) -> bool:
        """True when the OTP verification flow is active.

        True for smtp/resend/console providers, and also when DEBUG is set
        (DEBUG skips delivery and logs the OTP instead — the long-standing
        local-development behavior). Only EMAIL_PROVIDER=none without DEBUG
        disables verification.
        """
        return self.DEBUG or self.EMAIL_PROVIDER != "none"


settings = Settings()
