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

    @field_serializer("otp_expiry")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
