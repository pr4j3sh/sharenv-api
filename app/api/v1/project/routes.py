from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.project.exceptions import CreateProjectError, ProjectAlreadyExists
from app.api.v1.project.schemas import CreateProjectReq, CreateProjectRes
from app.api.v1.project.service import Project
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger

router = APIRouter(prefix="/project", tags=["Project"])

log = get_logger(__name__)


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
        log.exception("Project creation failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
