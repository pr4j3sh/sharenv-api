from app.api.v1.project.exceptions import CreateProjectError, ProjectAlreadyExists
from app.api.v1.project.schemas import CreateProjectReq, CreateProjectRes
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

        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project_exists = await self.db.projects.find_one(
            {"name": payload.name, "user_id": user_id}
        )
        if project_exists:
            raise ProjectAlreadyExists("project already exists")

        now = get_current_time()

        project_payload = {
            "name": payload.name,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }

        res = await self.db.projects.insert_one(project_payload)

        if not res or not res.inserted_id:
            raise CreateProjectError("failed to create project")

        return CreateProjectRes(project_id=str(res.inserted_id))
