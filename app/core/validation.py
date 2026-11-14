from __future__ import annotations

import json
import re
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.core.config import settings

PROJECT_ENV_NAME_RE = re.compile(r"^[a-z0-9_-]+$")
VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_object_id(value: str, *, label: str = "id") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"invalid {label}") from e


def ensure_variable_name(name: str) -> str:
    try:
        return validate_variable_name(name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def ensure_project_env_name(value: str, *, kind: str) -> str:
    try:
        return validate_project_env_name(value, kind=kind)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def validate_variable_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Variable name must be a string")
    if not name:
        raise ValueError("Variable name must not be empty")
    if len(name) > settings.MAX_VARIABLE_NAME_LENGTH:
        raise ValueError(
            f"Variable name must be at most "
            f"{settings.MAX_VARIABLE_NAME_LENGTH} characters"
        )
    if not VARIABLE_NAME_RE.fullmatch(name):
        raise ValueError(
            "Variable name must start with a letter or underscore and contain only "
            "letters, numbers, and underscores"
        )
    return name


def validate_project_env_name(value: str, *, kind: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{kind} name must be a string")
    if not value:
        raise ValueError(f"{kind} name must not be empty")
    if len(value) > settings.MAX_PROJECT_ENV_NAME_LENGTH:
        raise ValueError(
            f"{kind} name must be at most "
            f"{settings.MAX_PROJECT_ENV_NAME_LENGTH} characters"
        )
    if not PROJECT_ENV_NAME_RE.fullmatch(value):
        raise ValueError(
            f"{kind} name must contain only lowercase letters, numbers, hyphens, "
            "and underscores."
        )
    return value


def validate_variable_value_size(value: Any) -> Any:
    try:
        encoded = json.dumps(value).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise ValueError("Variable value must be a JSON-serializable scalar") from e
    if len(encoded) > settings.MAX_VARIABLE_VALUE_BYTES:
        raise ValueError(
            f"Variable value must be at most {settings.MAX_VARIABLE_VALUE_BYTES} bytes"
        )
    return value
