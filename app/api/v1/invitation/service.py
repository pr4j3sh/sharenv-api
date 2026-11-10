from datetime import datetime, timedelta

from bson.errors import InvalidId
from bson.objectid import ObjectId

from app.api.v1.auth.exceptions import UserNotFound
from app.api.v1.invitation.exceptions import (
    InvalidInvitationEnvironments,
    InvitationAlreadyAccepted,
    InvitationAlreadyExists,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
)
from app.api.v1.invitation.models import InvitationModel
from app.api.v1.invitation.schemas import (
    AcceptInvitationRes,
    CancelInvitationRes,
    CreateInvitationReq,
    CreateInvitationRes,
    GetInvitationRes,
)
from app.api.v1.project.exceptions import (
    CannotModifyOwner,
    ProjectNotFound,
    ReauthenticationFailed,
)
from app.api.v1.project.permissions import resolve_access
from app.core.config import settings
from app.core.crypto import generate_invitation_token, hash_secret
from app.core.email import send_invitation_email
from app.core.logger import get_logger
from app.core.security import verify_password
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Invitation:
    def __init__(self) -> None:
        self.db = mongo

    async def _reauthenticate(self, user_id: str, password: str) -> None:
        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("password") or not verify_password(
            password, user["password"]
        ):
            raise ReauthenticationFailed("re-authentication failed")

    async def _get_owned_project(self, user_id: str, project_id: str) -> dict:
        if self.db.projects is None:
            raise RuntimeError("mongodb is not connected")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(project_id), "user_id": user_id}
        )
        if not project:
            raise ProjectNotFound("project does not exist")
        return project

    async def _validate_environments(
        self, project_id: str, environment_ids: list[str]
    ) -> list[str]:
        if not environment_ids:
            return []

        if self.db.environments is None:
            raise RuntimeError("mongodb is not connected")

        # de-dupe, preserve order
        unique_ids = list(dict.fromkeys(environment_ids))

        try:
            env_oids = [ObjectId(eid) for eid in unique_ids]
        except (InvalidId, TypeError) as e:
            raise InvalidInvitationEnvironments(
                "one or more environments do not exist"
            ) from e

        found = await self.db.environments.find(
            {"_id": {"$in": env_oids}, "project_id": project_id}
        ).to_list(length=None)
        found_ids = {str(e["_id"]) for e in found}
        missing = [eid for eid in unique_ids if eid not in found_ids]
        if missing:
            raise InvalidInvitationEnvironments(
                "one or more environments do not exist"
            )

        return unique_ids

    async def create_invitation(
        self, user_id: str, project_id: str, payload: CreateInvitationReq
    ) -> CreateInvitationRes:
        log.info("creating invitation for project %s", project_id)

        if (
            self.db.projects is None
            or self.db.users is None
            or self.db.invitations is None
        ):
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, payload.password)
        project = await self._get_owned_project(user_id, project_id)

        email = payload.email.strip().lower()

        # Cannot invite self (owner).
        owner = await self.db.users.find_one({"_id": ObjectId(project["user_id"])})
        if owner and owner.get("email", "").strip().lower() == email:
            raise CannotModifyOwner("cannot invite the project owner")

        # If the invitee already has an account, ensure they aren't already a member.
        invitee = await self.db.users.find_one({"email": email})
        if invitee:
            invitee_id = str(invitee["_id"])
            if resolve_access(project, invitee_id) is not None:
                raise InvitationAlreadyExists("user is already a member of the project")

        env_ids = await self._validate_environments(project_id, payload.environments)

        now = get_current_time()

        # Disallow a duplicate pending (unaccepted, unexpired) invitation.
        existing = await self.db.invitations.find_one(
            {
                "project_id": project_id,
                "email": email,
                "accepted_at": None,
                "expires_at": {"$gt": now.isoformat()},
            }
        )
        if existing:
            raise InvitationAlreadyExists("a pending invitation already exists")

        token = generate_invitation_token()
        expires_at = now + timedelta(days=settings.INVITATION_EXPIRY_DAYS)

        invitation = InvitationModel(
            project_id=project_id,
            email=email,
            role=payload.role,
            environments=env_ids,
            invited_by=user_id,
            token_hash=hash_secret(token),
            created_at=now,
            expires_at=expires_at,
        )

        res = await self.db.invitations.insert_one(
            invitation.model_dump(by_alias=True, exclude_none=True)
        )
        if not res or not res.inserted_id:
            raise InvitationNotFound("failed to create invitation")

        try:
            await send_invitation_email(
                to=email,
                project_name=project["name"],
                role=payload.role,
                token=token,
            )
        except Exception:
            # Roll back so we don't leave an undeliverable invitation.
            await self.db.invitations.delete_one({"_id": res.inserted_id})
            raise

        return CreateInvitationRes(
            invitation_id=str(res.inserted_id),
            project_id=project_id,
            email=email,
            role=payload.role,
            environments=env_ids,
            expires_at=expires_at,
        )

    async def get_invitations(
        self, user_id: str, project_id: str
    ) -> list[GetInvitationRes]:
        log.info("listing invitations for project %s", project_id)

        if self.db.invitations is None:
            raise RuntimeError("mongodb is not connected")

        await self._get_owned_project(user_id, project_id)

        invitations = await self.db.invitations.find(
            {"project_id": project_id}
        ).to_list(length=None)

        return [GetInvitationRes.model_validate(i) for i in invitations]

    async def cancel_invitation(
        self, user_id: str, project_id: str, invitation_id: str, password: str
    ) -> CancelInvitationRes:
        log.info("canceling invitation %s", invitation_id)

        if self.db.invitations is None:
            raise RuntimeError("mongodb is not connected")

        await self._reauthenticate(user_id, password)
        await self._get_owned_project(user_id, project_id)

        try:
            inv_oid = ObjectId(invitation_id)
        except (InvalidId, TypeError) as e:
            raise InvitationNotFound("invitation not found") from e

        res = await self.db.invitations.delete_one(
            {"_id": inv_oid, "project_id": project_id}
        )
        if not res.deleted_count:
            raise InvitationNotFound("invitation not found")

        return CancelInvitationRes(invitation_id=invitation_id)

    async def accept_invitation(
        self, user_id: str, token: str
    ) -> AcceptInvitationRes:
        log.info("accepting invitation")

        if (
            self.db.invitations is None
            or self.db.projects is None
            or self.db.users is None
        ):
            raise RuntimeError("mongodb is not connected")

        token_hash = hash_secret(token)
        invitation = await self.db.invitations.find_one({"token_hash": token_hash})
        if not invitation:
            raise InvitationNotFound("invitation not found")

        if invitation.get("accepted_at") is not None:
            raise InvitationAlreadyAccepted("invitation already accepted")

        now = get_current_time()
        expires_at = invitation["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if now >= expires_at:
            raise InvitationExpired("invitation expired")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise UserNotFound("user not found")

        if not user.get("is_verified"):
            raise InvitationEmailMismatch("email not verified")

        user_email = (user.get("email") or "").strip().lower()
        if user_email != invitation["email"]:
            raise InvitationEmailMismatch("invitation email does not match")

        project = await self.db.projects.find_one(
            {"_id": ObjectId(invitation["project_id"])}
        )
        if not project:
            raise ProjectNotFound("project does not exist")

        # Ensure not already a member/owner.
        if resolve_access(project, user_id) is not None:
            # Mark accepted to avoid reuse if somehow pending.
            await self.db.invitations.update_one(
                {"_id": invitation["_id"], "accepted_at": None},
                {"$set": {"accepted_at": now.isoformat()}},
            )
            raise InvitationAlreadyAccepted("user is already a member of the project")

        member = {
            "user_id": user_id,
            "role": invitation["role"],
            "environments": invitation.get("environments", []),
        }

        # Claim the invitation atomically, then add the member.
        claimed = await self.db.invitations.find_one_and_update(
            {"_id": invitation["_id"], "accepted_at": None},
            {"$set": {"accepted_at": now.isoformat()}},
        )
        if not claimed:
            raise InvitationAlreadyAccepted("invitation already accepted")

        res = await self.db.projects.update_one(
            {
                "_id": ObjectId(invitation["project_id"]),
                "members.user_id": {"$ne": user_id},
            },
            {"$push": {"members": member}},
        )
        if not res.matched_count:
            raise ProjectNotFound("project does not exist")

        return AcceptInvitationRes(
            project_id=invitation["project_id"],
            role=invitation["role"],
            environments=invitation.get("environments", []),
        )
