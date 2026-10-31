from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    EnvironmentAlreadyExists,
    EnvironmentNotFound,
)
from app.api.v1.environment.models import EnvironmentModel
from app.api.v1.environment.schemas import CreateEnvironmentReq, CreateEnvironmentRes
from app.api.v1.environment.service import Environment
from app.api.v1.project.exceptions import ProjectNotFound
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger

router = APIRouter(prefix="/environment", tags=["Environment"])

log = get_logger(__name__)


@router.get("/{project_id}/{environment_name}", response_model=EnvironmentModel)
async def get_environment_by_name(
    project_id: str,
    environment_name: str,
    _: Annotated[str, Depends(get_current_user_id)],
):
    try:
        e = Environment()
        res = await e.get_environment_by_name(project_id, environment_name)
        log.info(res)
        return res
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Fetching environment failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/{project_id}", response_model=CreateEnvironmentRes)
async def create_environemnt(
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
        log.exception("Environment creation failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
