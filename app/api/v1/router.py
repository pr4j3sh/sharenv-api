from fastapi import APIRouter

from app.api.v1.auth.routes import router as auth
from app.api.v1.environment.routes import router as environment
from app.api.v1.project.routes import router as project
from app.api.v1.variable.routes import router as variable

router = APIRouter(prefix="/v1")

router.include_router(auth)
router.include_router(project)
router.include_router(environment)
router.include_router(variable)
