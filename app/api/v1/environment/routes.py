from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.v1.auth.exceptions import UnauthorizedAccess
from app.api.v1.environment.exceptions import (
    CreateEnvironmentError,
    DeleteEnvironmentFailed,
    EnvironmentAlreadyExists,
    EnvironmentNotFound,
    EnvironmentQuotaExceeded,
)
from app.api.v1.environment.models import EnvironmentModel
from app.api.v1.environment.schemas import (
    CreateEnvironmentReq,
    CreateEnvironmentRes,
    DeleteEnvironmentRes,
)
from app.api.v1.environment.service import Environment
from app.api.v1.project.exceptions import ProjectNotFound
from app.api.v1.variable.exceptions import DeleteVariableFailed
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger
from app.core.pagination import set_pagination_headers
from app.core.config import settings
from app.core.validation import ensure_project_env_name, parse_object_id

router = APIRouter(prefix="/environment", tags=["Environment"])

log = get_logger(__name__)


@router.get("/{project_id}", response_model=list[EnvironmentModel])
async def get_environments(
    project_id: str,
    response: Response,
    user_id: Annotated[str, Depends(get_current_user_id)],
    environment_name: str = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=settings.PAGINATION_MAX_LIMIT)] = settings.PAGINATION_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    parse_object_id(project_id, label="project_id")
    if environment_name is not None:
        ensure_project_env_name(environment_name, kind="Environment")
    try:
        e = Environment()
        res, total = await e.get_environments(user_id, project_id, environment_name, limit, offset)
        set_pagination_headers(
            response, total=total, limit=limit, offset=offset, item_count=len(res)
        )
        return res
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("fetching environments failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/{project_id}", response_model=CreateEnvironmentRes)
async def create_environemnt(
    project_id: str,
    req: CreateEnvironmentReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(project_id, label="project_id")
    try:
        e = Environment()
        res = await e.create_environemnt(user_id, project_id, req)
        return res
    except ProjectNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except EnvironmentAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except EnvironmentQuotaExceeded as e:
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
        log.exception("creating environments failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{project_id}/{environment_name}", response_model=DeleteEnvironmentRes)
async def delete_environemnt_by_name(
    project_id: str,
    environment_name: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(project_id, label="project_id")
    ensure_project_env_name(environment_name, kind="Environment")
    try:
        e = Environment()
        res = await e.delete_environment_by_name(user_id, project_id, environment_name)
        return res
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except DeleteVariableFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except DeleteEnvironmentFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("deleting environment failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{environment_id}", response_model=DeleteEnvironmentRes)
async def delete_environemnt(
    environment_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(environment_id, label="environment_id")
    try:
        e = Environment()
        res = await e.delete_environment(user_id, environment_id)
        return res
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except DeleteVariableFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except DeleteEnvironmentFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("deleting environment failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
