"""Shared input validation helpers and limits."""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

# Names: project/environment are lowercase slug-like; variables follow a safe
# env/dotenv identifier shape to prevent `.env` injection (newline/=/#/etc.)
# and to keep the AAD-bound name unambiguous.
PROJECT_ENV_NAME_RE = re.compile(r"^[a-z0-9_-]+$")
VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_PROJECT_ENV_NAME_LENGTH = 64
MAX_VARIABLE_NAME_LENGTH = 128
MAX_VARIABLE_VALUE_BYTES = 64 * 1024
MAX_EMAIL_LENGTH = 254
MAX_OTP_LENGTH = 16
MAX_REFRESH_TOKEN_LENGTH = 4096
MAX_INVITATION_TOKEN_LENGTH = 512
MAX_REQUEST_BODY_BYTES = 256 * 1024

# Quotas (defaults; enforced in services)
DEFAULT_MAX_PROJECTS_PER_USER = 50
DEFAULT_MAX_ENVIRONMENTS_PER_PROJECT = 50
DEFAULT_MAX_VARIABLES_PER_ENVIRONMENT = 500
DEFAULT_MAX_TOTAL_VALUE_BYTES_PER_PROJECT = 5 * 1024 * 1024


def parse_object_id(value: str, *, label: str = "id") -> ObjectId:
    """Parse a path/body identifier or raise a 400 HTTP error."""
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
    if len(name) > MAX_VARIABLE_NAME_LENGTH:
        raise ValueError(
            f"Variable name must be at most {MAX_VARIABLE_NAME_LENGTH} characters"
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
    if len(value) > MAX_PROJECT_ENV_NAME_LENGTH:
        raise ValueError(
            f"{kind} name must be at most {MAX_PROJECT_ENV_NAME_LENGTH} characters"
        )
    if not PROJECT_ENV_NAME_RE.fullmatch(value):
        raise ValueError(
            f"{kind} name must contain only lowercase letters, numbers, hyphens, "
            "and underscores."
        )
    return value


def validate_variable_value_size(value: Any) -> Any:
    # Values are JSON-serialized for encryption; bound the serialized size.
    import json

    try:
        encoded = json.dumps(value).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise ValueError("Variable value must be a JSON-serializable scalar") from e
    if len(encoded) > MAX_VARIABLE_VALUE_BYTES:
        raise ValueError(
            f"Variable value must be at most {MAX_VARIABLE_VALUE_BYTES} bytes"
        )
    return value
