from bson.objectid import ObjectId

from app.api.v1.auth.exceptions import UnauthorizedAccess, UserNotFound
from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    EnvironmentAlreadyExists,
)
from app.api.v1.environment.models import EnvironmentModel
from app.api.v1.environment.schemas import CreateEnvironmentReq, CreateEnvironmentRes
from app.api.v1.project.exceptions import ProjectNotFound
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

        if (
            self.db.environments is None
            or self.db.projects is None
            or self.db.users is None
        ):
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise UserNotFound("User does not exist")

        project = await self.db.projects.find_one(
            {
                "_id": ObjectId(project_id),
                "$or": [{"user_id": user_id}, {"users": user_id}],
            }
        )
        if not project:
            raise ProjectNotFound("Project does not exist")

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

        res = await self.db.environments.insert_one(
            environment_payload.model_dump(
                by_alias=True,
                exclude_none=True,
            )
        )

        if not res or not res.inserted_id:
            raise CreateEnvironmentError("failed to create environment")

        return CreateEnvironmentRes(environment_id=str(res.inserted_id))

    async def get_environments(
        self, user_id: str, project_id: str, environment_name: str | None = None
    ) -> list[EnvironmentModel]:
        log.info(f"fetching environments {user_id} {project_id}")

        if (
            self.db.environments is None
            or self.db.projects is None
            or self.db.users is None
        ):
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise UserNotFound("User does not exist")

        project = await self.db.projects.find_one({"_id": ObjectId(project_id)})

        if not project:
            raise ProjectNotFound("Project does not exist")

        user_exists = await self.db.projects.find_one(
            {
                "_id": ObjectId(project_id),
                "$or": [
                    {"user_id": user_id},
                    {"users": user_id},
                ],
            }
        )

        if not user_exists:
            raise UnauthorizedAccess("Unauthorized Access")

        query = {"project_id": project_id}

        if environment_name is not None:
            query["name"] = environment_name

        environments = await self.db.environments.find(query).to_list(length=None)

        return [
            EnvironmentModel.model_validate(environment) for environment in environments
        ]
