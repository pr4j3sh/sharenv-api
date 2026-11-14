from datetime import datetime

from app.core.serialization import SerializableDocument


class UserModel(SerializableDocument):
    email: str
    password: str
    is_verified: bool = False
    otp: str | None = None
    otp_expiry: datetime | None = None
    # Bumping token_version revokes every token (access and refresh) issued
    # for the user; logout and refresh-token replay increment it.
    token_version: int = 0
    # jti of the currently valid refresh token; rotated on every use.
    refresh_jti: str | None = None
