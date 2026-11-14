from datetime import datetime

from app.core.serialization import MongoDocument


class VariableModel(MongoDocument):
    name: str
    value_enc: str
    key_version: int
    environment_id: str
    # Plaintext serialized value size in bytes; used for quota accounting.
    value_size: int = 0
    created_at: datetime
    updated_at: datetime
