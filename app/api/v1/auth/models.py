from datetime import datetime

from app.core.serialization import SerializableDocument


class UserModel(SerializableDocument):
    email: str
    password: str
    is_verified: bool = False
    otp: str | None = None
    otp_expiry: datetime | None = None
    token_version: int = 0
    refresh_jti: str | None = None
    previous_refresh_jti: str | None = None
    rotated_at: datetime | None = None
