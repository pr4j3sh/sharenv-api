from typing import Any

from bson import ObjectId

from app.api.v1.project.exceptions import ProjectNotFound, ReauthenticationFailed
from app.core.config import settings
from app.core.rate_limit import reauth_failures
from app.core.security import verify_password
from app.db.mongodb import mongo


async def reauthenticate_user(user_id: str, password: str) -> None:
    if mongo.users is None:
        raise RuntimeError("mongodb is not connected")

    retry_after = await reauth_failures.locked(
        f"reauth:{user_id}",
        settings.LOGIN_FAILURE_LIMIT,
        settings.LOGIN_LOCKOUT_MINUTES * 60,
    )
    if retry_after:
        raise ReauthenticationFailed("re-authentication failed")

    user = await mongo.users.find_one({"_id": ObjectId(user_id)})

    if (
        not user
        or not user.get("password")
        or not verify_password(password, user["password"])
    ):
        await reauth_failures.record(
            f"reauth:{user_id}", settings.LOGIN_LOCKOUT_MINUTES * 60
        )
        raise ReauthenticationFailed("re-authentication failed")

    await reauth_failures.clear(f"reauth:{user_id}")


async def get_owned_project(user_id: str, project_id: str) -> dict[str, Any]:
    if mongo.projects is None:
        raise RuntimeError("mongodb is not connected")

    project = await mongo.projects.find_one(
        {"_id": ObjectId(project_id), "user_id": user_id}
    )
    if not project:
        raise ProjectNotFound("project does not exist")
    result: dict[str, Any] = project
    return result
