from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    EnvironmentAlreadyExists,
)
from app.api.v1.environment.schemas import CreateEnvironmentReq, CreateEnvironmentRes
from app.api.v1.environment.service import Environment
from app.api.v1.project.exceptions import ProjectNotFound
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger

router = APIRouter(prefix="/environment", tags=["Environment"])

log = get_logger(__name__)


@router.post("/{project_id}", response_model=CreateEnvironmentRes)
async def create_project(
    project_id: str,
    req: CreateEnvironmentReq,
    _: Annotated[str, Depends(get_current_user_id)],
):
    try:
        e = Environment()
        res = await e.create_environemnt(project_id, req)
        return res
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except CreateEnvironmentError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Project creation failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
