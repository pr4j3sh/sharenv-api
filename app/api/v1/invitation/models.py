from datetime import datetime

from pydantic import Field

from app.core.serialization import MongoDocument


class InvitationModel(MongoDocument):
    project_id: str
    email: str
    role: str
    environments: list[str] = Field(default_factory=list)
    invited_by: str
    token_hash: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
