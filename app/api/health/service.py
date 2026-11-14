import asyncio

from app.api.health.schemas import CheckState, HealthRes, ReadyRes
from app.core.config import settings
from app.db.mongodb import mongo


class Health:
    def __init__(self) -> None:
        self.db = mongo

    async def liveness(self) -> HealthRes:
        """The process is up and serving; no dependency checks."""
        return HealthRes()

    async def readiness(self) -> ReadyRes:
        """The app can serve traffic; every dependency check must pass."""
        checks: dict[str, CheckState] = {"mongo": await self._mongo_status()}
        status: CheckState = (
            "ok" if all(state == "ok" for state in checks.values()) else "unavailable"
        )
        return ReadyRes(status=status, checks=checks)

    async def _mongo_status(self) -> CheckState:
        if self.db.db is None:
            return "unavailable"
        try:
            await asyncio.wait_for(
                self.db.db.command("ping"), settings.MONGO_PING_TIMEOUT_SECONDS
            )
        except Exception:
            return "unavailable"
        return "ok"
