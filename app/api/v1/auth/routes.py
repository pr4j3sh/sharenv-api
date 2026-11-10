from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.auth.exceptions import (
    CreateTokenError,
    EmailNotConfigured,
    InvalidCredentials,
    InvalidRefreshToken,
    LogoutError,
    RegisterError,
    ResendOtpError,
    SendEmailError,
    TooManyAttempts,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserNotFound,
    UserNotVerified,
    VerifyOtpError,
)
from app.api.v1.auth.schemas import (
    LoginReq,
    LoginRes,
    LogoutRes,
    RefreshReq,
    RefreshRes,
    RegisterReq,
    RegisterRes,
    ResendOtpRes,
    VerifyUserReq,
    VerifyUserRes,
)
from app.api.v1.auth.service import Auth
from app.core.dependencies import get_current_user_id
from app.core.logger import get_logger
from app.core.rate_limit import enforce_auth_ip_limit
from app.core.validation import parse_object_id

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    dependencies=[Depends(enforce_auth_ip_limit)],
)

log = get_logger(__name__)


def _too_many_attempts(e: TooManyAttempts) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Too many requests",
        headers={"Retry-After": str(e.retry_after)},
    )


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
    except SendEmailError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except TooManyAttempts as e:
        raise _too_many_attempts(e) from e
    except Exception as e:
        log.exception("registration failed unexpectedly")
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
    except InvalidCredentials as e:
        # Unknown email and wrong password land here identically.
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except UserNotVerified as e:
        raise HTTPException(
            status_code=403,
            detail="email_not_verified",
        ) from e
    except TooManyAttempts as e:
        raise _too_many_attempts(e) from e
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("login failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/refresh", response_model=RefreshRes)
async def refresh(req: RefreshReq):
    try:
        a = Auth()
        res = await a.refresh(req.refresh_token)
        return res
    except InvalidRefreshToken as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except TooManyAttempts as e:
        raise _too_many_attempts(e) from e
    except Exception as e:
        log.exception("token refresh failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/logout", response_model=LogoutRes)
async def logout(user_id: Annotated[str, Depends(get_current_user_id)]):
    try:
        a = Auth()
        res = await a.logout(user_id)
        return res
    except LogoutError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("logout failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/verify/{user_id}", response_model=VerifyUserRes)
async def verify_user(user_id: str, req: VerifyUserReq):
    parse_object_id(user_id, label="user_id")
    try:
        a = Auth()
        res = await a.verify_user(user_id, req.otp)
        return res
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except EmailNotConfigured as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except UserAlreadyVerified as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except VerifyOtpError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except TooManyAttempts as e:
        raise _too_many_attempts(e) from e
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("user verification failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/resend/{user_id}", response_model=ResendOtpRes)
async def resend_otp(user_id: str):
    parse_object_id(user_id, label="user_id")
    try:
        a = Auth()
        res = await a.resent_otp(user_id)
        return res
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except EmailNotConfigured as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except UserAlreadyVerified as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e
    except ResendOtpError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except SendEmailError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except TooManyAttempts as e:
        raise _too_many_attempts(e) from e
    except Exception as e:
        log.exception("otp resend failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
