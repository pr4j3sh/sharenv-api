from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError

from app.api.v1.auth.exceptions import UnauthorizedAccess
from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    DeleteEnvironmentFailed,
    EnvironmentAlreadyExists,
    EnvironmentNotFound,
    EnvironmentQuotaExceeded,
)
from app.api.v1.environment.models import EnvironmentModel
from app.api.v1.environment.schemas import (
    CreateEnvironmentReq,
    CreateEnvironmentRes,
    DeleteEnvironmentRes,
)
from app.api.v1.project.exceptions import ProjectNotFound
from app.api.v1.project.permissions import resolve_access
from app.api.v1.variable.exceptions import DeleteVariableFailed
from app.core.config import settings
from app.core.logger import get_logger
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Environment:
    def __init__(self) -> None:
        self.db = mongo

    async def create_environemnt(
        self, user_id: str, project_id: str, payload: CreateEnvironmentReq
    ) -> CreateEnvironmentRes:
        log.info(f"creating environment {project_id} {payload}")

        if self.db.environments is None or self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ProjectNotFound("Project does not exist")

        access = resolve_access(project, user_id)
        if access is None:
            raise ProjectNotFound("Project does not exist")
        if not access.can_write():
            raise UnauthorizedAccess("Unauthorized Access")

        env_count = await self.db.environments.count_documents({"project_id": project_id})
        if env_count >= settings.MAX_ENVIRONMENTS_PER_PROJECT:
            raise EnvironmentQuotaExceeded("environment quota exceeded")

        environment_exists = await self.db.environments.find_one(
            {"name": payload.name, "project_id": project_id}
        )
        if environment_exists:
            raise EnvironmentAlreadyExists("environment already exists")

        now = get_current_time()

        environment_payload = EnvironmentModel(
            name=payload.name,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )

        try:
            res = await self.db.environments.insert_one(
                environment_payload.model_dump(
                    by_alias=True,
                    exclude_none=True,
                )
            )
        except DuplicateKeyError as e:
            raise EnvironmentAlreadyExists("environment already exists") from e

        if not res or not res.inserted_id:
            raise CreateEnvironmentError("failed to create environment")

        # Note: writer-created environments are not auto-granted; owner controls
        # env access grants explicitly.
        return CreateEnvironmentRes(environment_id=str(res.inserted_id))

    async def get_environments(
        self, user_id: str, project_id: str, environment_name: str | None = None
    ) -> list[EnvironmentModel]:
        log.info(f"fetching environments {user_id} {project_id}")

        if self.db.environments is None or self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ProjectNotFound("Project does not exist")

        access = resolve_access(project, user_id)
        if access is None:
            raise UnauthorizedAccess("Unauthorized Access")

        query: dict = {"project_id": project_id}

        if access.environments is not None:
            if not access.environments:
                return []
            query["_id"] = {"$in": [ObjectId(eid) for eid in access.environments]}

        if environment_name is not None:
            query["name"] = environment_name

        environments = await self.db.environments.find(query).to_list(length=None)

        return [
            EnvironmentModel.model_validate(environment) for environment in environments
        ]

    async def delete_environment(self, user_id: str, environment_id: str):
        log.info(f"deleting environment {environment_id}")

        if (
            self.db.environments is None
            or self.db.projects is None
            or self.db.variables is None
        ):
            raise RuntimeError("mongodb is not connected")

        environment = await self.db.environments.find_one(
            {"_id": ObjectId(environment_id)}
        )

        if not environment:
            raise EnvironmentNotFound("environment does not exist")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(environment["project_id"])}
        )
        if not project:
            raise UnauthorizedAccess("Unauthorized Access")

        access = resolve_access(project, user_id)
        if access is None or not access.can_access_env(environment_id):
            raise UnauthorizedAccess("Unauthorized Access")
        if not access.can_write():
            raise UnauthorizedAccess("Unauthorized Access")

        res = await self.db.variables.delete_many({"environment_id": environment_id})
        if not res.acknowledged:
            raise DeleteVariableFailed(
                "Failed to delete variables for this envrionment"
            )

        res = await self.db.environments.delete_one({"_id": ObjectId(environment_id)})

        if not res.acknowledged:
            raise DeleteEnvironmentFailed("Failed to delete environment")

        return DeleteEnvironmentRes(environment_id=environment_id)

    async def delete_environment_by_name(
        self, user_id: str, project_id: str, environment_name: str
    ):
        log.info(f"deleting environment {project_id} {environment_name}")

        if (
            self.db.environments is None
            or self.db.projects is None
            or self.db.variables is None
        ):
            raise RuntimeError("mongodb is not connected")

        environment = await self.db.environments.find_one(
            {"project_id": project_id, "name": environment_name}
        )

        if not environment:
            raise EnvironmentNotFound("environment does not exist")

        environment_id = str(environment["_id"])

        project = await self.db.projects.find_one(
            {"_id": ObjectId(environment["project_id"])}
        )
        if not project:
            raise UnauthorizedAccess("Unauthorized Access")

        access = resolve_access(project, user_id)
        if access is None or not access.can_access_env(environment_id):
            raise UnauthorizedAccess("Unauthorized Access")
        if not access.can_write():
            raise UnauthorizedAccess("Unauthorized Access")

        res = await self.db.variables.delete_many({"environment_id": environment_id})
        if not res.acknowledged:
            raise DeleteVariableFailed(
                "Failed to delete variables for this envrionment"
            )

        res = await self.db.environments.delete_one({"_id": environment["_id"]})

        if not res.acknowledged:
            raise DeleteEnvironmentFailed("Failed to delete environment")

        return DeleteEnvironmentRes(environment_id=environment_id)
