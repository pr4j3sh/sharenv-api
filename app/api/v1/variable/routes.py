from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.environment.exceptions import EnvironmentNotFound
from app.api.v1.variable.exceptions import CreateVariableError, VariableAlreadyExists
from app.api.v1.variable.schemas import CreateVariableReq, CreateVariableRes
from app.api.v1.variable.service import Variable
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger

router = APIRouter(prefix="/variable", tags=["Variable"])

log = get_logger(__name__)


@router.post("/{environment_id}", response_model=CreateVariableRes)
async def create_variable(
    environment_id: str,
    req: CreateVariableReq,
    _: Annotated[str, Depends(get_current_user_id)],
):
    try:
        v = Variable()
        res = await v.create_variable(environment_id, req)
        return res
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except VariableAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except CreateVariableError as e:
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
