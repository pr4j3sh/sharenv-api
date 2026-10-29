from bson.objectid import ObjectId

from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    EnvironmentAlreadyExists,
)
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
        self, project_id: str, payload: CreateEnvironmentReq
    ) -> CreateEnvironmentRes:
        log.info(f"creating environment {project_id} {payload}")

        if self.db.environments is None or self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = self.db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ProjectNotFound("Project does not exist")

        environment_exists = self.db.environments.find_one(
            {"name": payload.name, "project_id": project_id}
        )
        if environment_exists:
            raise EnvironmentAlreadyExists("environment already exists")

        now = get_current_time()

        environment_payload = {
            "name": payload.name,
            "project_id": project_id,
            "created_at": now,
            "updated_at": now,
        }
        res = await self.db.environments.insert_one(environment_payload)

        if not res or not res.inserted_id:
            raise CreateEnvironmentError("failed to create environment")

        return CreateEnvironmentRes(environment_id=str(res.inserted_id))
