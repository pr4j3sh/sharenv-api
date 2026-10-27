from fastapi import APIRouter

from app.api.v1.auth.schemas import LoginReq, LoginRes, RegisterReq, RegisterRes
from app.api.v1.auth.service import Auth

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=RegisterRes)
async def register(req: RegisterReq):
    a = Auth()
    res = await a.register(req)
    return res


@router.post("/login", response_model=LoginRes)
async def login(req: LoginReq):
    a = Auth()
    res = await a.login(req)
    return res
