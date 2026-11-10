from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.project.exceptions import (
    CannotModifyOwner,
    CreateProjectError,
    MemberNotFound,
    ProjectAlreadyExists,
    ProjectNotFound,
    ReauthenticationFailed,
)
from app.api.v1.project.schemas import (
    CreateProjectReq,
    CreateProjectRes,
    DeleteProjectReq,
    DeleteProjectRes,
    GetProjectsRes,
    LeaveProjectRes,
    RemoveMemberReq,
    RemoveMemberRes,
    UpdateMemberAccessReq,
    UpdateMemberAccessRes,
)
from app.api.v1.project.service import Project
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger

router = APIRouter(prefix="/project", tags=["Project"])

log = get_logger(__name__)


@router.get("/", response_model=list[GetProjectsRes])
async def get_projects(
    user_id: Annotated[str, Depends(get_current_user_id)],
    project_name: str = Query(default=None),
):
    try:
        p = Project()
        res = await p.get_projects(user_id, project_name)
        return res
    except Exception as e:
        log.exception("fetching projects failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/", response_model=CreateProjectRes)
async def create_project(
    req: CreateProjectReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.create_project(user_id, req)
        return res
    except ProjectAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except CreateProjectError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("creating project failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.patch(
    "/{project_id}/members/{member_id}", response_model=UpdateMemberAccessRes
)
async def update_member_access(
    project_id: str,
    member_id: str,
    req: UpdateMemberAccessReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.update_member_access(user_id, project_id, member_id, req)
        return res
    except ReauthenticationFailed as e:
        raise HTTPException(
            status_code=403,
            detail="re-authentication failed",
        ) from e
    except CannotModifyOwner as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except MemberNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("updating member access failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{project_id}/members/me", response_model=LeaveProjectRes)
async def leave_project(
    project_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.leave_project(user_id, project_id)
        return res
    except CannotModifyOwner as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except MemberNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("leaving project failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{project_id}/members/{member_id}", response_model=RemoveMemberRes)
async def remove_member(
    project_id: str,
    member_id: str,
    req: RemoveMemberReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.remove_member(user_id, project_id, member_id, req.password)
        return res
    except ReauthenticationFailed as e:
        raise HTTPException(
            status_code=403,
            detail="re-authentication failed",
        ) from e
    except CannotModifyOwner as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except MemberNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("removing member failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{project_id}", response_model=DeleteProjectRes)
async def delete_project(
    project_id: str,
    req: DeleteProjectReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.delete_project(user_id, project_id, req.password)
        return res
    except ReauthenticationFailed as e:
        raise HTTPException(
            status_code=403,
            detail="re-authentication failed",
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("deleting project failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/name/{project_name}", response_model=DeleteProjectRes)
async def delete_project_by_name(
    project_name: str,
    req: DeleteProjectReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.delete_project_by_name(user_id, project_name, req.password)
        return res
    except ReauthenticationFailed as e:
        raise HTTPException(
            status_code=403,
            detail="re-authentication failed",
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("deleting project failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
