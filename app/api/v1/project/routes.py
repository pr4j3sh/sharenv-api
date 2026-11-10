from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.auth.exceptions import UserNotFound
from app.api.v1.project.exceptions import (
    CannotAddSameUser,
    CreateProjectError,
    ProjectAlreadyExists,
    ProjectNotFound,
    ReauthenticationFailed,
)
from app.api.v1.project.schemas import (
    AddUserReq,
    AddUserRes,
    CreateProjectReq,
    CreateProjectRes,
    DeleteProjectReq,
    DeleteProjectRes,
    GetProjectsRes,
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


@router.put("/{project_id}", response_model=AddUserRes)
async def add_user(
    project_id: str,
    req: AddUserReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        p = Project()
        res = await p.add_user(user_id, project_id, req)
        return res
    except ReauthenticationFailed as e:
        raise HTTPException(
            status_code=403,
            detail="re-authentication failed",
        ) from e
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except CannotAddSameUser as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("adding user to project failed unexpectedly")
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
