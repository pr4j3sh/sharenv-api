from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class UserModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    email: str
    password: str
    is_verified: bool = False
    otp: str
    otp_expiry: datetime
    # Bumping token_version revokes every token (access and refresh) issued
    # for the user; logout and refresh-token replay increment it.
    token_version: int = 0
    # jti of the currently valid refresh token; rotated on every use.
    refresh_jti: str | None = None

    @field_serializer("otp_expiry")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
