from bson.objectid import ObjectId

from app.api.v1.auth.exceptions import UnauthorizedAccess
from app.api.v1.environment.exceptions import EnvironmentNotFound
from app.api.v1.variable.exceptions import CreateVariableError, VariableAlreadyExists
from app.api.v1.variable.models import VariableModel
from app.api.v1.variable.schemas import (
    CreateVariableReq,
    CreateVariableRes,
    VariableRes,
)
from app.core.config import settings
from app.core.crypto import decrypt_value, encrypt_value
from app.core.logger import get_logger
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Variable:
    def __init__(self) -> None:
        self.db = mongo

    async def _get_environment_for_user(
        self, user_id: str, environment_id: str
    ) -> dict:
        if self.db.environments is None or self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        environment = await self.db.environments.find_one(
            {"_id": ObjectId(environment_id)}
        )
        if not environment:
            raise EnvironmentNotFound("Environment does not exist")

        project = await self.db.projects.find_one(
            {
                "_id": ObjectId(environment["project_id"]),
                "$or": [{"user_id": user_id}, {"users": user_id}],
            }
        )
        if not project:
            raise UnauthorizedAccess("Unauthorized Access")

        return environment

    async def create_variable(
        self, user_id: str, environment_id: str, payload: CreateVariableReq
    ) -> CreateVariableRes:
        log.info(f"creating variable {environment_id}")

        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        await self._get_environment_for_user(user_id, environment_id)

        variable_exists = await self.db.variables.find_one(
            {"name": payload.name, "environment_id": environment_id}
        )
        if variable_exists:
            raise VariableAlreadyExists("variable already exists")

        now = get_current_time()

        variable_payload = VariableModel(
            name=payload.name,
            value_enc=encrypt_value(payload.value, environment_id, payload.name),
            key_version=settings.ENCRYPTION_KEY_VERSION,
            environment_id=environment_id,
            created_at=now,
            updated_at=now,
        )

        res = await self.db.variables.insert_one(
            variable_payload.model_dump(by_alias=True, exclude_none=True)
        )

        if not res or not res.inserted_id:
            raise CreateVariableError("failed to create variable")

        return CreateVariableRes(variable_id=str(res.inserted_id))

    async def get_variables(
        self, user_id: str, environment_id: str
    ) -> list[VariableRes]:
        log.info(f"fetching variables {environment_id}")

        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        await self._get_environment_for_user(user_id, environment_id)

        variables = await self.db.variables.find(
            {"environment_id": environment_id}
        ).to_list(length=None)

        res = []

        for variable in variables:
            model = VariableModel.model_validate(variable)
            res.append(
                VariableRes(
                    id=str(model.id),
                    name=model.name,
                    value=decrypt_value(
                        model.value_enc, model.environment_id, model.name
                    ),
                    environment_id=model.environment_id,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
            )

        return res
