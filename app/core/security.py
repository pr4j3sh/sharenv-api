import secrets
from datetime import timedelta
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.utils import get_current_time

password_hash = PasswordHash.recommended()

# Verified against when the email is unknown so login timing cannot be used
# to distinguish existing accounts: an Argon2 verify costs the same whether
# or not the hash corresponds to a real user.
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def _create_token(subject: str, token_version: int, typ: str) -> tuple[str, str]:
    now = get_current_time()
    jti = uuid4().hex

    if typ == "access":
        expiry = now + timedelta(minutes=settings.JWT_EXPIRY)
    else:
        expiry = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_DAYS)

    payload = {
        "sub": subject,
        "typ": typ,
        "jti": jti,
        "ver": token_version,
        "iat": now,
        "exp": expiry,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token, jti


def create_access_token(subject: str, token_version: int) -> str:
    token, _ = _create_token(subject, token_version, "access")
    return token


def create_refresh_token(subject: str, token_version: int) -> tuple[str, str]:
    """Returns (token, jti); the jti is stored to make the token single-use."""
    return _create_token(subject, token_version, "refresh")


def _decode_token(token: str, expected_typ: str) -> dict:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "jti", "ver", "typ"]},
    )

    if payload.get("typ") != expected_typ:
        raise jwt.InvalidTokenError(f"expected a {expected_typ} token")

    return payload


def decode_access_token(token: str) -> dict:
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> dict:
    return _decode_token(token, "refresh")
