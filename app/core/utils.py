from datetime import UTC, datetime

from app.core.config import settings


def get_current_time():
    return datetime.now(UTC)


def validate_password_size(password: str) -> str:
    if len(password.encode("utf-8")) > settings.MAX_PASSWORD_BYTES:
        raise ValueError("Password must not exceed 1024 bytes")

    return password
