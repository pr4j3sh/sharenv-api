import json

from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError

from app.api.v1.auth.exceptions import UnauthorizedAccess
from app.api.v1.environment.exceptions import EnvironmentNotFound
from app.api.v1.project.permissions import resolve_access
from app.api.v1.variable.exceptions import (
    CreateVariableError,
    DeleteVariableFailed,
    UpdateVariableFailed,
    VariableAlreadyExists,
    VariableNotFound,
    VariableQuotaExceeded,
)
from app.api.v1.variable.models import VariableModel
from app.api.v1.variable.schemas import (
    CreateVariableReq,
    CreateVariableRes,
    DeleteVariableRes,
    GetVariablesRes,
    UpdateVariableReq,
    UpdateVariableRes,
)
from app.core.config import settings
from app.core.crypto import decrypt_value, encrypt_value, unwrap_data_key
from app.core.logger import get_logger
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Variable:
    def __init__(self) -> None:
        self.db = mongo

    @staticmethod
    def _value_size(value) -> int:
        return len(json.dumps(value).encode("utf-8"))

    async def _project_value_bytes(self, project_id: str) -> int:
        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        envs = await self.db.environments.find(
            {"project_id": project_id}, {"_id": 1}
        ).to_list(length=None)
        env_ids = [str(e["_id"]) for e in envs]
        if not env_ids:
            return 0

        pipeline = [
            {"$match": {"environment_id": {"$in": env_ids}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_size"}}},
        ]
        agg = await self.db.variables.aggregate(pipeline).to_list(length=1)
        if not agg:
            return 0
        return int(agg[0].get("total") or 0)

    async def _get_environment_for_user(
        self, user_id: str, environment_id: str, *, write: bool = False
    ) -> tuple[dict, dict]:
        if self.db.environments is None or self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        environment = await self.db.environments.find_one(
            {"_id": ObjectId(environment_id)}
        )
        if not environment:
            raise EnvironmentNotFound("Environment does not exist")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(environment["project_id"])}
        )
        if not project:
            raise UnauthorizedAccess("Unauthorized Access")

        access = resolve_access(project, user_id)
        if access is None or not access.can_access_env(environment_id):
            raise UnauthorizedAccess("Unauthorized Access")
        if write and not access.can_write():
            raise UnauthorizedAccess("Unauthorized Access")

        return environment, project

    async def _get_variable_for_user(
        self, user_id: str, variable_id: str, *, write: bool = False
    ) -> tuple[dict, dict]:
        if (
            self.db.environments is None
            or self.db.projects is None
            or self.db.variables is None
        ):
            raise RuntimeError("mongodb is not connected")

        variable = await self.db.variables.find_one({"_id": ObjectId(variable_id)})
        if not variable:
            raise VariableNotFound("Variable does not exist")

        environment = await self.db.environments.find_one(
            {"_id": ObjectId(variable["environment_id"])}
        )
        if not environment:
            raise EnvironmentNotFound("Environment does not exist")

        env_id = str(environment["_id"])
        project = await self.db.projects.find_one(
            {"_id": ObjectId(environment["project_id"])}
        )
        if not project:
            raise UnauthorizedAccess("Unauthorized Access")

        access = resolve_access(project, user_id)
        if access is None or not access.can_access_env(env_id):
            raise UnauthorizedAccess("Unauthorized Access")
        if write and not access.can_write():
            raise UnauthorizedAccess("Unauthorized Access")

        return variable, project

    async def create_variable(
        self, user_id: str, environment_id: str, payload: CreateVariableReq
    ) -> CreateVariableRes:
        log.info(f"creating variable {environment_id}")

        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        _, project = await self._get_environment_for_user(
            user_id, environment_id, write=True
        )

        var_count = await self.db.variables.count_documents(
            {"environment_id": environment_id}
        )
        if var_count >= settings.MAX_VARIABLES_PER_ENVIRONMENT:
            raise VariableQuotaExceeded("variable quota exceeded")

        project_id = str(project["_id"])
        new_size = self._value_size(payload.value)
        total_bytes = await self._project_value_bytes(project_id)
        if total_bytes + new_size > settings.MAX_TOTAL_VALUE_BYTES_PER_PROJECT:
            raise VariableQuotaExceeded("project value size quota exceeded")

        variable_exists = await self.db.variables.find_one(
            {"name": payload.name, "environment_id": environment_id}
        )
        if variable_exists:
            raise VariableAlreadyExists("variable already exists")

        data_key = unwrap_data_key(project["data_key"], project["key_version"])
        now = get_current_time()

        variable_payload = VariableModel(
            name=payload.name,
            value_enc=encrypt_value(
                payload.value,
                data_key,
                project_id,
                environment_id,
                payload.name,
                settings.ENCRYPTION_KEY_VERSION,
            ),
            key_version=settings.ENCRYPTION_KEY_VERSION,
            environment_id=environment_id,
            value_size=new_size,
            created_at=now,
            updated_at=now,
        )

        try:
            res = await self.db.variables.insert_one(
                variable_payload.model_dump(by_alias=True, exclude_none=True)
            )
        except DuplicateKeyError as e:
            raise VariableAlreadyExists("variable already exists") from e

        if not res or not res.inserted_id:
            raise CreateVariableError("failed to create variable")

        return CreateVariableRes(variable_id=str(res.inserted_id))

    async def get_variables(
        self, user_id: str, environment_id: str
    ) -> list[GetVariablesRes]:
        log.info(f"fetching variables {environment_id}")

        if self.db.environments is None or self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        _, project = await self._get_environment_for_user(
            user_id, environment_id, write=False
        )

        variables = await self.db.variables.find(
            {"environment_id": environment_id}
        ).to_list(length=None)

        data_key = unwrap_data_key(project["data_key"], project["key_version"])
        project_id = str(project["_id"])
        res = []

        for variable in variables:
            model = VariableModel.model_validate(variable)
            try:
                value = decrypt_value(
                    model.value_enc,
                    data_key,
                    project_id,
                    model.environment_id,
                    model.name,
                    model.key_version,
                )

                res.append(
                    GetVariablesRes(
                        _id=str(model.id),
                        name=model.name,
                        value=value,
                        environment_id=model.environment_id,
                        created_at=model.created_at,
                        updated_at=model.updated_at,
                    )
                )

            except Exception:
                log.exception(
                    "failed to decrypt variable %s in environment %s",
                    model.name,
                    environment_id,
                )

                res.append(
                    GetVariablesRes(
                        _id=str(model.id),
                        name=model.name,
                        value=None,
                        environment_id=model.environment_id,
                        created_at=model.created_at,
                        updated_at=model.updated_at,
                        undecryptable=True,
                    )
                )

        return res

    async def delete_variable(self, user_id, variable_id) -> DeleteVariableRes:
        log.info(f"deleting variable {variable_id}")

        if self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        variable, _ = await self._get_variable_for_user(
            user_id, variable_id, write=True
        )

        res = await self.db.variables.delete_one({"_id": variable["_id"]})

        if not res.acknowledged:
            raise DeleteVariableFailed("Failed to delete variable")

        return DeleteVariableRes(variable_id=variable_id)

    async def delete_variable_by_name(
        self, user_id: str, environment_id: str, variable_name: str
    ) -> DeleteVariableRes:
        log.info(f"deleting variable {environment_id} {variable_name}")

        if self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        await self._get_environment_for_user(user_id, environment_id, write=True)

        res = await self.db.variables.find_one_and_delete(
            {"name": variable_name, "environment_id": environment_id}
        )

        if res is None:
            raise VariableNotFound("variable not found")

        return DeleteVariableRes(variable_id=str(res["_id"]))

    async def update_variable(
        self, user_id, variable_id, payload: UpdateVariableReq
    ) -> UpdateVariableRes:
        log.info(f"updating variable {variable_id}")

        if self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        variable, project = await self._get_variable_for_user(
            user_id, variable_id, write=True
        )

        project_id = str(project["_id"])
        new_size = self._value_size(payload.value)
        old_size = int(variable.get("value_size") or 0)
        total_bytes = await self._project_value_bytes(project_id)
        if total_bytes - old_size + new_size > settings.MAX_TOTAL_VALUE_BYTES_PER_PROJECT:
            raise VariableQuotaExceeded("project value size quota exceeded")

        data_key = unwrap_data_key(project["data_key"], project["key_version"])

        now = get_current_time()
        res = await self.db.variables.update_one(
            {"_id": variable["_id"]},
            {
                "$set": {
                    "value_enc": encrypt_value(
                        payload.value,
                        data_key,
                        project_id,
                        variable["environment_id"],
                        variable["name"],
                        settings.ENCRYPTION_KEY_VERSION,
                    ),
                    "key_version": settings.ENCRYPTION_KEY_VERSION,
                    "value_size": new_size,
                    "updated_at": now.isoformat(),
                },
            },
        )

        if not res.acknowledged:
            raise UpdateVariableFailed("Failed to update variable")

        return UpdateVariableRes(variable_id=variable_id)

    async def update_variable_by_name(
        self,
        user_id: str,
        environment_id: str,
        variable_name: str,
        payload: UpdateVariableReq,
    ) -> UpdateVariableRes:
        log.info(f"updating variable {environment_id} {variable_name}")

        if self.db.variables is None:
            raise RuntimeError("mongodb is not connected")

        _, project = await self._get_environment_for_user(
            user_id, environment_id, write=True
        )

        existing = await self.db.variables.find_one(
            {"name": variable_name, "environment_id": environment_id}
        )
        if existing is None:
            raise VariableNotFound("variable not found")

        project_id = str(project["_id"])
        new_size = self._value_size(payload.value)
        old_size = int(existing.get("value_size") or 0)
        total_bytes = await self._project_value_bytes(project_id)
        if total_bytes - old_size + new_size > settings.MAX_TOTAL_VALUE_BYTES_PER_PROJECT:
            raise VariableQuotaExceeded("project value size quota exceeded")

        data_key = unwrap_data_key(project["data_key"], project["key_version"])

        now = get_current_time()
        res = await self.db.variables.find_one_and_update(
            {"name": variable_name, "environment_id": environment_id},
            {
                "$set": {
                    "value_enc": encrypt_value(
                        payload.value,
                        data_key,
                        project_id,
                        environment_id,
                        variable_name,
                        settings.ENCRYPTION_KEY_VERSION,
                    ),
                    "key_version": settings.ENCRYPTION_KEY_VERSION,
                    "value_size": new_size,
                    "updated_at": now.isoformat(),
                },
            },
        )

        if res is None:
            raise VariableNotFound("variable not found")

        return UpdateVariableRes(variable_id=str(res["_id"]))
