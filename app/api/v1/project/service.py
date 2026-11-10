from bson.objectid import ObjectId

from app.api.v1.auth.exceptions import UserNotFound
from app.api.v1.project.exceptions import (
    CannotAddSameUser,
    CreateProjectError,
    ProjectAlreadyExists,
    ProjectNotFound,
)
from app.api.v1.project.models import ProjectModel
from app.api.v1.project.schemas import (
    AddUserReq,
    AddUserRes,
    CreateProjectReq,
    CreateProjectRes,
    DeleteProjectRes,
    GetProjectsRes,
)
from app.core.config import settings
from app.core.crypto import get_data_key, wrap_data_key
from app.core.logger import get_logger
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Project:
    def __init__(self) -> None:
        self.db = mongo

    async def create_project(
        self, user_id: str, payload: CreateProjectReq
    ) -> CreateProjectRes:
        log.info(f"creating project {user_id} {payload}")

        if self.db.projects is None or self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise UserNotFound("User does not exist")

        project_exists = await self.db.projects.find_one(
            {"name": payload.name, "user_id": user_id}
        )
        if project_exists:
            raise ProjectAlreadyExists("project already exists")

        data_key = get_data_key()
        wrapped_key = wrap_data_key(data_key)
        now = get_current_time()

        project_payload = ProjectModel(
            name=payload.name,
            user_id=user_id,
            data_key=wrapped_key,
            key_version=settings.ENCRYPTION_KEY_VERSION,
            created_at=now,
            updated_at=now,
        )

        res = await self.db.projects.insert_one(
            project_payload.model_dump(
                by_alias=True,
                exclude_none=True,
            )
        )

        if not res or not res.inserted_id:
            raise CreateProjectError("failed to create project")

        return CreateProjectRes(project_id=str(res.inserted_id))

    async def add_user(
        self, user_id: str, project_id: str, payload: AddUserReq
    ) -> AddUserRes:
        log.info(f"creating project {user_id} {project_id}")

        if self.db.projects is None or self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user_exists = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user_exists:
            raise UserNotFound("User does not exist")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )
        if not project:
            raise ProjectNotFound("project does not exist")

        user = await self.db.users.find_one({"email": payload.email.strip().lower()})

        if not user:
            raise UserNotFound("User does not exist")

        if user_id == str(user.get("_id")):
            raise CannotAddSameUser("Cannot add same user")

        res = await self.db.projects.find_one_and_update(
            {"_id": ObjectId(project_id)},
            {"$addToSet": {"users": str(user.get("_id"))}},
        )

        if not res:
            raise ProjectNotFound("project does not exist")

        return AddUserRes(project_id=project_id)

    async def get_projects(
        self, user_id: str, project_name: str | None = None
    ) -> list[GetProjectsRes]:
        log.info(f"fetching projects {user_id}")

        if self.db.projects is None or self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user_exists = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user_exists:
            raise UserNotFound("User does not exist")

        query: dict[str, list[dict[str, str]] | str] = {
            "$or": [{"user_id": user_id}, {"users": user_id}]
        }

        if project_name is not None:
            query["name"] = project_name

        projects = await self.db.projects.find(query).to_list(length=None)

        return [GetProjectsRes.model_validate(project) for project in projects]

    async def delete_project(self, user_id: str, project_id: str) -> DeleteProjectRes:
        log.info(f"deleting project {project_id}")

        if (
            self.db.projects is None
            or self.db.users is None
            or self.db.environments is None
            or self.db.variables is None
        ):
            raise RuntimeError("mongodb is not connected")

        user_exists = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user_exists:
            raise UserNotFound("User does not exist")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )
        if not project:
            raise ProjectNotFound("project does not exist")

        environments = await self.db.environments.find(
            {"project_id": project_id}
        ).to_list(length=None)

        environment_ids = [str(environment["_id"]) for environment in environments]

        for environment_id in environment_ids:
            await self.db.variables.delete_many({"environment_id": environment_id})

        await self.db.environments.delete_many({"project_id": project_id})

        await self.db.projects.delete_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )

        return DeleteProjectRes(project_id=project_id)

    async def delete_project_by_name(
        self, user_id: str, project_name: str
    ) -> DeleteProjectRes:
        log.info(f"deleting project {project_name}")

        if (
            self.db.projects is None
            or self.db.users is None
            or self.db.environments is None
            or self.db.variables is None
        ):
            raise RuntimeError("mongodb is not connected")

        user_exists = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user_exists:
            raise UserNotFound("User does not exist")

        project = await self.db.projects.find_one(
            {"name": project_name, "user_id": user_id}
        )

        if not project:
            raise ProjectNotFound("project does not exist")

        environments = await self.db.environments.find(
            {"project_id": str(project["_id"])}
        ).to_list(length=None)

        environment_ids = [str(environment["_id"]) for environment in environments]

        for environment_id in environment_ids:
            await self.db.variables.delete_many({"environment_id": environment_id})

        await self.db.environments.delete_many({"project_id": str(project["_id"])})

        await self.db.projects.delete_one({"_id": project["_id"], "user_id": user_id})

        return DeleteProjectRes(project_id=str(project["_id"]))
