from dataclasses import dataclass
from typing import Literal

Role = Literal["owner", "writer", "reader"]


@dataclass(frozen=True)
class Access:
    role: Role
    # None means all environments (owner). For members, the explicit grant list.
    environments: list[str] | None

    def can_read(self) -> bool:
        return self.role in {"owner", "writer", "reader"}

    def can_write(self) -> bool:
        return self.role in {"owner", "writer"}

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    def can_access_env(self, environment_id: str) -> bool:
        if self.environments is None:
            return True
        return environment_id in self.environments


def resolve_access(project: dict, user_id: str) -> Access | None:
    if project.get("user_id") == user_id:
        return Access(role="owner", environments=None)

    for member in project.get("members", []):
        if member.get("user_id") == user_id:
            role = member.get("role")
            if role not in {"writer", "reader"}:
                return None
            envs = member.get("environments") or []
            return Access(role=role, environments=list(envs))

    return None
