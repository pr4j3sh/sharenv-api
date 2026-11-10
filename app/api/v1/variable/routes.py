from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.auth.exceptions import UnauthorizedAccess
from app.api.v1.environment.exceptions import EnvironmentNotFound
from app.api.v1.variable.exceptions import (
    CreateVariableError,
    DeleteVariableFailed,
    UpdateVariableFailed,
    VariableAlreadyExists,
    VariableNotFound,
    VariableQuotaExceeded,
)
from app.api.v1.variable.schemas import (
    CreateVariableReq,
    CreateVariableRes,
    DeleteVariableRes,
    GetVariablesRes,
    UpdateVariableReq,
    UpdateVariableRes,
)
from app.api.v1.variable.service import Variable
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger
from app.core.validation import ensure_variable_name, parse_object_id

router = APIRouter(prefix="/variable", tags=["Variable"])

log = get_logger(__name__)


@router.get("/{environment_id}", response_model=list[GetVariablesRes])
async def get_variables(
    environment_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(environment_id, label="environment_id")
    try:
        v = Variable()
        res = await v.get_variables(user_id, environment_id)
        return res
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("fetching variables failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/{environment_id}", response_model=CreateVariableRes)
async def create_variable(
    environment_id: str,
    req: CreateVariableReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(environment_id, label="environment_id")
    try:
        v = Variable()
        res = await v.create_variable(user_id, environment_id, req)
        return res
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except VariableAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except VariableQuotaExceeded as e:
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
        log.exception("creating variable failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{environment_id}/{variable_name}", response_model=DeleteVariableRes)
async def delete_variable_by_name(
    environment_id: str,
    variable_name: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(environment_id, label="environment_id")
    ensure_variable_name(variable_name)
    try:
        v = Variable()
        res = await v.delete_variable_by_name(user_id, environment_id, variable_name)
        return res
    except VariableNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("deleting variable failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.delete("/{variable_id}", response_model=DeleteVariableRes)
async def delete_variable(
    variable_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(variable_id, label="variable_id")
    try:
        v = Variable()
        res = await v.delete_variable(user_id, variable_id)
        return res
    except VariableNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
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
    except Exception as e:
        log.exception("deleting variable failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.put("/{environment_id}/{variable_name}", response_model=UpdateVariableRes)
async def update_variable_by_name(
    environment_id: str,
    variable_name: str,
    req: UpdateVariableReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(environment_id, label="environment_id")
    ensure_variable_name(variable_name)
    try:
        v = Variable()
        res = await v.update_variable_by_name(
            user_id, environment_id, variable_name, req
        )
        return res
    except VariableNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except VariableQuotaExceeded as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except UpdateVariableFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("updating variable failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.put("/{variable_id}", response_model=UpdateVariableRes)
async def update_variable(
    variable_id: str,
    req: UpdateVariableReq,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    parse_object_id(variable_id, label="variable_id")
    try:
        v = Variable()
        res = await v.update_variable(user_id, variable_id, req)
        return res
    except VariableNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except EnvironmentNotFound as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UnauthorizedAccess as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        ) from e
    except VariableQuotaExceeded as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except UpdateVariableFailed as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("updating variable failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
