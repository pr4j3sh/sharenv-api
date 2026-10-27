from fastapi import APIRouter

from app.api.v1.auth.routes import router as auth

router = APIRouter(prefix="/v1")

router.include_router(auth)
