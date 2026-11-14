from typing import Literal

from pydantic import BaseModel, Field

CheckState = Literal["ok", "unavailable"]


def _default_checks() -> dict[str, Literal["ok"]]:
    return {"app": "ok"}


class HealthRes(BaseModel):
    status: Literal["ok"] = "ok"
    checks: dict[str, Literal["ok"]] = Field(default_factory=_default_checks)


class ReadyRes(BaseModel):
    status: CheckState
    checks: dict[str, CheckState]
