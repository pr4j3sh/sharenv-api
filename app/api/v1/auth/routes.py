from fastapi import APIRouter, HTTPException

from app.api.v1.auth.exceptions import (
    CreateTokenError,
    InvalidCredentials,
    RegisterError,
    UserAlreadyExists,
    UserNotFound,
)
from app.api.v1.auth.schemas import LoginReq, LoginRes, RegisterReq, RegisterRes
from app.api.v1.auth.service import Auth
from app.core.logger import get_logger

router = APIRouter(prefix="/auth", tags=["Auth"])

log = get_logger(__name__)


@router.post("/register", response_model=RegisterRes)
async def register(req: RegisterReq):
    try:
        a = Auth()
        res = await a.register(req)
        return res
    except UserAlreadyExists as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except RegisterError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Registration failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/login", response_model=LoginRes)
async def login(req: LoginReq):
    try:
        a = Auth()
        res = await a.login(req)
        return res
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except InvalidCredentials as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Login failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
