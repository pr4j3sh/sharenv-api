from typing import Annotated

import jwt
from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.mongodb import mongo

bearer_scheme = HTTPBearer()

_NOT_AUTHENTICATED = {"WWW-Authenticate": "Bearer"}


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(bearer_scheme),
    ],
) -> str:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_NOT_AUTHENTICATED,
        ) from e

    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=_NOT_AUTHENTICATED,
        )

    try:
        user_oid = ObjectId(user_id)
    except (InvalidId, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=_NOT_AUTHENTICATED,
        ) from e

    if mongo.users is None:
        raise RuntimeError("mongodb is not connected")

    # Re-check the user on every request: a deleted user loses access
    # immediately, and a bumped token_version revokes all their tokens.
    user = await mongo.users.find_one({"_id": user_oid}, {"token_version": 1})

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_NOT_AUTHENTICATED,
        )

    if payload.get("ver") != user.get("token_version", 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_NOT_AUTHENTICATED,
        )

    return user_id
