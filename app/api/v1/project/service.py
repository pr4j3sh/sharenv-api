from bson.errors import InvalidId
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError

from app.api.v1.project.exceptions import (
    CannotModifyOwner,
    CreateProjectError,
    ForbiddenAccess,
    MemberNotFound,
    ProjectAlreadyExists,
    ProjectNotFound,
    ProjectQuotaExceeded,
    ReauthenticationFailed,
)
from app.api.v1.project.models import ProjectModel
from app.api.v1.project.permissions import resolve_access
from app.api.v1.project.schemas import (
    CreateProjectReq,
    CreateProjectRes,
    DeleteProjectRes,
    GetProjectsRes,
    LeaveProjectRes,
    RemoveMemberRes,
    UpdateMemberAccessReq,
    UpdateMemberAccessRes,
)
from app.core.config import settings
from app.core.crypto import get_data_key, wrap_data_key
from app.core.logger import get_logger
from app.core.security import verify_password
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Project:
    def __init__(self) -> None:
        self.db = mongo

    async def _reauthenticate(self, user_id: str, password: str) -> None:
        """Require the caller's current password for sensitive actions."""
        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user or not user.get("password") or not verify_password(
            password, user["password"]
        ):
            raise ReauthenticationFailed("re-authentication failed")

    async def _get_project_for_owner(self, user_id: str, project_id: str) -> dict:
        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )
        if not project:
            raise ProjectNotFound("project does not exist")
        return project

    async def create_project(
        self, user_id: str, payload: CreateProjectReq
    ) -> CreateProjectRes:
        log.info(f"creating project {user_id} {payload}")

        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project_count = await self.db.projects.count_documents({"user_id": user_id})
        if project_count >= settings.MAX_PROJECTS_PER_USER:
            raise ProjectQuotaExceeded("project quota exceeded")

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

        try:
            res = await self.db.projects.insert_one(
                project_payload.model_dump(
                    by_alias=True,
                    exclude_none=True,
                )
            )
        except DuplicateKeyError as e:
            raise ProjectAlreadyExists("project already exists") from e

        if not res or not res.inserted_id:
            raise CreateProjectError("failed to create project")

        return CreateProjectRes(project_id=str(res.inserted_id))

    async def get_projects(
        self,
        user_id: str,
        project_name: str | None = None,
        limit: int = settings.PAGINATION_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> tuple[list[GetProjectsRes], int]:
        log.info(f"fetching projects {user_id}")

        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        query: dict = {
            "$or": [{"user_id": user_id}, {"members.user_id": user_id}]
        }

        if project_name is not None:
            query["name"] = project_name

        total = await self.db.projects.count_documents(query)
        projects = (
            await self.db.projects.find(query)
            .sort([("created_at", 1), ("_id", 1)])
            .skip(offset)
            .limit(limit)
            .to_list(length=limit)
        )

        results: list[GetProjectsRes] = []
        for project in projects:
            access = resolve_access(project, user_id)
            if access is None:
                continue
            results.append(
                GetProjectsRes(
                    _id=project["_id"],
                    name=project["name"],
                    user_id=project["user_id"],
                    role=access.role,
                    created_at=project["created_at"],
                    updated_at=project["updated_at"],
                )
            )

        return results, total

    async def delete_project(
        self, user_id: str, project_id: str, password: str
    ) -> DeleteProjectRes:
        log.info(f"deleting project {project_id}")

        if (
            self.db.projects is None
            or self.db.users is None
            or self.db.environments is None
            or self.db.variables is None
            or self.db.invitations is None
        ):
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, password)

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
        await self.db.invitations.delete_many({"project_id": project_id})

        await self.db.projects.delete_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )

        return DeleteProjectRes(project_id=project_id)

    async def delete_project_by_name(
        self, user_id: str, project_name: str, password: str
    ) -> DeleteProjectRes:
        log.info(f"deleting project {project_name}")

        if (
            self.db.projects is None
            or self.db.users is None
            or self.db.environments is None
            or self.db.variables is None
            or self.db.invitations is None
        ):
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, password)

        project = await self.db.projects.find_one(
            {"name": project_name, "user_id": user_id}
        )

        if not project:
            raise ProjectNotFound("project does not exist")

        project_id = str(project["_id"])

        environments = await self.db.environments.find(
            {"project_id": project_id}
        ).to_list(length=None)

        environment_ids = [str(environment["_id"]) for environment in environments]

        for environment_id in environment_ids:
            await self.db.variables.delete_many({"environment_id": environment_id})

        await self.db.environments.delete_many({"project_id": project_id})
        await self.db.invitations.delete_many({"project_id": project_id})

        await self.db.projects.delete_one({"_id": project["_id"], "user_id": user_id})

        return DeleteProjectRes(project_id=project_id)

    async def update_member_access(
        self, user_id: str, project_id: str, member_id: str, payload: UpdateMemberAccessReq
    ) -> UpdateMemberAccessRes:
        log.info(f"updating member access {project_id} {member_id}")

        if self.db.projects is None or self.db.environments is None:
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, payload.password)
        project = await self._get_project_for_owner(user_id, project_id)

        if member_id == project["user_id"]:
            raise CannotModifyOwner("cannot modify project owner")

        members = project.get("members", [])
        member = next((m for m in members if m.get("user_id") == member_id), None)
        if member is None:
            raise MemberNotFound("member not found")

        # Validate that every granted environment belongs to this project.
        if payload.environments:
            try:
                env_oids = [ObjectId(eid) for eid in payload.environments]
            except (InvalidId, TypeError) as e:
                raise ProjectNotFound("one or more environments do not exist") from e
            found = await self.db.environments.find(
                {"_id": {"$in": env_oids}, "project_id": project_id}
            ).to_list(length=None)
            found_ids = {str(e["_id"]) for e in found}
            missing = [eid for eid in payload.environments if eid not in found_ids]
            if missing:
                raise ProjectNotFound("one or more environments do not exist")

        new_role = payload.role or member.get("role", "reader")
        new_envs = list(dict.fromkeys(payload.environments))  # de-dupe, preserve order

        res = await self.db.projects.update_one(
            {"_id": project["_id"], "members.user_id": member_id},
            {"$set": {"members.$.role": new_role, "members.$.environments": new_envs}},
        )

        if not res.matched_count:
            raise MemberNotFound("member not found")

        return UpdateMemberAccessRes(
            project_id=project_id,
            user_id=member_id,
            role=new_role,
            environments=new_envs,
        )

    async def remove_member(
        self, user_id: str, project_id: str, member_id: str, password: str
    ) -> RemoveMemberRes:
        log.info(f"removing member {project_id} {member_id}")

        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, password)
        project = await self._get_project_for_owner(user_id, project_id)

        if member_id == project["user_id"]:
            raise CannotModifyOwner("cannot remove project owner")

        res = await self.db.projects.update_one(
            {"_id": project["_id"]},
            {"$pull": {"members": {"user_id": member_id}}},
        )

        if not res.matched_count:
            raise ProjectNotFound("project does not exist")
        if not res.modified_count:
            raise MemberNotFound("member not found")

        return RemoveMemberRes(project_id=project_id, user_id=member_id)

    async def leave_project(self, user_id: str, project_id: str) -> LeaveProjectRes:
        log.info(f"leaving project {project_id} {user_id}")

        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ProjectNotFound("project does not exist")

        access = resolve_access(project, user_id)
        if access is None:
            raise ProjectNotFound("project does not exist")

        if access.is_owner:
            raise CannotModifyOwner("project owner cannot leave the project")

        res = await self.db.projects.update_one(
            {"_id": project["_id"]},
            {"$pull": {"members": {"user_id": user_id}}},
        )

        if not res.modified_count:
            raise MemberNotFound("member not found")

        return LeaveProjectRes(project_id=project_id, user_id=user_id)
