from fastapi import APIRouter, Response

from app.api.health.schemas import HealthRes, ReadyRes
from app.api.health.service import Health

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthRes)
async def health() -> HealthRes:
    return await Health().liveness()


@router.get(
    "/health/ready",
    response_model=ReadyRes,
    responses={503: {"model": ReadyRes, "description": "A dependency check failed"}},
)
async def ready(response: Response) -> ReadyRes:
    result = await Health().readiness()
    if result.status != "ok":
        response.status_code = 503
    return result
