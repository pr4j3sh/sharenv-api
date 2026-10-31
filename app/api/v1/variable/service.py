from bson.objectid import ObjectId

from app.api.v1.environment.exceptions import EnvironmentNotFound
from app.api.v1.variable.exceptions import CreateVariableError, VariableAlreadyExists
from app.api.v1.variable.schemas import CreateVariableReq, CreateVariableRes
from app.core.logger import get_logger
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Variable:
    def __init__(self) -> None:
        self.db = mongo

    async def create_variable(
        self, environment_id: str, payload: CreateVariableReq
    ) -> CreateVariableRes:
        log.info(f"creating variable {environment_id} {payload}")

        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.environments.find_one({"_id": ObjectId(environment_id)})
        if not project:
            raise EnvironmentNotFound("Environment does not exist")

        variable_exists = await self.db.variables.find_one(
            {"name": payload.name, "environment_id": environment_id}
        )
        if variable_exists:
            raise VariableAlreadyExists("variable already exists")

        now = get_current_time()

        variable_payload = {
            "name": payload.name,
            "value": payload.value,
            "environment_id": environment_id,
            "created_at": now,
            "updated_at": now,
        }
        res = await self.db.variables.insert_one(variable_payload)

        if not res or not res.inserted_id:
            raise CreateVariableError("failed to create variable")

        return CreateVariableRes(variable_id=str(res.inserted_id))
