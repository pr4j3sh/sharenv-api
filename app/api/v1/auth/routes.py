from fastapi import APIRouter, HTTPException

from app.api.v1.auth.exceptions import (
    CreateTokenError,
    InvalidCredentials,
    RegisterError,
    ResendOtpError,
    SendEmailError,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserNotFound,
    UserNotVerified,
    VerifyOtpError,
)
from app.api.v1.auth.schemas import (
    LoginReq,
    LoginRes,
    RegisterReq,
    RegisterRes,
    ResendOtpRes,
    VerifyUserReq,
    VerifyUserRes,
)
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
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except UserNotVerified as e:
        raise HTTPException(
            status_code=403,
            detail="email_not_verified",
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
        log.exception("login failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e


@router.post("/verify/{user_id}", response_model=VerifyUserRes)
async def verify_user(user_id: str, req: VerifyUserReq):
    try:
        a = Auth()
        res = await a.verify_user(user_id, req.otp)
        return res
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
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
    try:
        a = Auth()
        res = await a.resent_otp(user_id)
        return res
    except UserNotFound as e:
        raise HTTPException(
            status_code=404,
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
    except CreateTokenError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("otp resend failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from e
