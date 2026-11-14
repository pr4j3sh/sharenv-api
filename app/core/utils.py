import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pwdlib import PasswordHash

_encryption_keys: dict[int, bytes] = {}
_master_ciphers: dict[int, AESGCM] = {}
_dummy_otp_hash: str = ""
_dummy_password_hash: str = ""


def get_current_time() -> datetime:
    return datetime.now(UTC)


def validate_password_size(password: str) -> str:
    from app.core.config import settings

    if len(password.encode("utf-8")) > settings.MAX_PASSWORD_BYTES:
        raise ValueError("Password must not exceed 1024 bytes")

    return password


def parse_key_registry(raw: str) -> dict[int, bytes]:
    global _encryption_keys

    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("key registry must be a valid JSON object") from e

    if not isinstance(registry, dict) or not registry:
        raise ValueError("key registry must be a non-empty JSON object")

    parsed: dict[int, bytes] = {}

    for version, key in registry.items():
        if not isinstance(version, str) or not version.isdigit():
            raise ValueError(
                f"key registry version {version!r} must be an integer string"
            )

        if not isinstance(key, str):
            raise TypeError(
                f"key registry entry for version {version} must be a base64 string"
            )

        try:
            decoded = base64.b64decode(key, validate=True)
        except Exception as e:
            raise ValueError(
                f"key registry entry for version {version} must be valid base64"
            ) from e

        if len(decoded) != 32:
            raise ValueError(
                f"key registry entry for version {version} must decode to 32 bytes"
            )

        if int(version) in parsed:
            raise ValueError(f"key registry has duplicate version {version}")

        parsed[int(version)] = decoded

    _encryption_keys = parsed
    return parsed


def encryption_keys() -> dict[int, bytes]:
    return _encryption_keys


def master_cipher(key_version: int) -> AESGCM:
    global _master_ciphers

    if not _master_ciphers:
        _master_ciphers = {
            version: AESGCM(key) for version, key in _encryption_keys.items()
        }

    cipher = _master_ciphers.get(key_version)
    if cipher is None:
        raise ValueError(f"key version {key_version} is not in the key registry")

    return cipher


def dummy_otp_hash() -> str:
    global _dummy_otp_hash

    if not _dummy_otp_hash:
        from app.core.config import settings

        value = secrets.token_urlsafe(32)
        _dummy_otp_hash = hmac.new(
            settings.JWT_SECRET.encode(), value.encode(), hashlib.sha256
        ).hexdigest()

    return _dummy_otp_hash


def dummy_password_hash() -> str:
    global _dummy_password_hash

    if not _dummy_password_hash:
        _dummy_password_hash = PasswordHash.recommended().hash(
            secrets.token_urlsafe(32)
        )

    return _dummy_password_hash


def allowed_hosts() -> list[str]:
    from app.core.config import settings

    return [host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()]
