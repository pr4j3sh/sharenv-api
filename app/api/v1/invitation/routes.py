from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.invitation.exceptions import (
    InvalidInvitationEnvironments,
    InvitationAlreadyAccepted,
    InvitationAlreadyExists,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
)
from app.api.v1.invitation.schemas import (
    AcceptInvitationRes,
    CancelInvitationReq,
    CancelInvitationRes,
    CreateInvitationReq,
    CreateInvitationRes,
    GetInvitationRes,
)
from app.api.v1.invitation.service import Invitation
from app.api.v1.project.exceptions import (
    CannotModifyOwner,
    ProjectNotFound,
    ReauthenticationFailed,
)
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger
from app.core.validation import MAX_INVITATION_TOKEN_LENGTH, parse_object_id

router = APIRouter(tags=["Invitation"])

log = get_logger(__name__)


@router.post(
    "/project/{project_id}/invitations", response_model=CreateInvitationRes
)
async def create_invitation(
    project_id: str,
    req: CreateInvitationReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(project_id, label="project_id")
    try:
        svc = Invitation()
        return await svc.create_invitation(user_id, project_id, req)
    except ReauthenticationFailed as e:
        raise HTTPException(status_code=403, detail="re-authentication failed") from e
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CannotModifyOwner as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvitationAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidInvitationEnvironments as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("creating invitation failed unexpectedly")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.get(
    "/project/{project_id}/invitations", response_model=list[GetInvitationRes]
)
async def get_invitations(
    project_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(project_id, label="project_id")
    try:
        svc = Invitation()
        return await svc.get_invitations(user_id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        log.exception("listing invitations failed unexpectedly")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.delete(
    "/project/{project_id}/invitations/{invitation_id}",
    response_model=CancelInvitationRes,
)
async def cancel_invitation(
    project_id: str,
    invitation_id: str,
    req: CancelInvitationReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(project_id, label="project_id")
    parse_object_id(invitation_id, label="invitation_id")
    try:
        svc = Invitation()
        return await svc.cancel_invitation(
            user_id, project_id, invitation_id, req.password
        )
    except ReauthenticationFailed as e:
        raise HTTPException(status_code=403, detail="re-authentication failed") from e
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvitationNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        log.exception("canceling invitation failed unexpectedly")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.post("/invitations/{token}/accept", response_model=AcceptInvitationRes)
async def accept_invitation(
    token: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not token or len(token) > MAX_INVITATION_TOKEN_LENGTH:
        raise HTTPException(status_code=400, detail="invalid invitation token")
    try:
        svc = Invitation()
        return await svc.accept_invitation(user_id, token)
    except InvitationNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvitationExpired as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except InvitationAlreadyAccepted as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvitationEmailMismatch as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        log.exception("accepting invitation failed unexpectedly")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e
