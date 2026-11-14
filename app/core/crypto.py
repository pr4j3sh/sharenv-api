import base64
import hashlib
import hmac
import json
import os
import secrets
import string

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import DUMMY_OTP_HASH as DUMMY_OTP_HASH
from app.core.config import MASTER_CIPHERS, settings


def generate_otp() -> str:
    length = settings.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_secret(value: str) -> str:
    return hmac.new(
        settings.JWT_SECRET.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def hash_otp(otp: str) -> str:
    return hash_secret(otp)


def verify_otp(stored_hash: str, otp: str) -> bool:
    return secrets.compare_digest(stored_hash, hash_otp(otp))


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def _master_cipher(key_version: int) -> AESGCM:
    cipher = MASTER_CIPHERS.get(key_version)
    if cipher is None:
        raise ValueError(f"key version {key_version} is not in the key registry")

    return cipher


def get_data_key() -> bytes:
    return secrets.token_bytes(settings.TOKEN_BYTES)


def wrap_data_key(data_key: bytes) -> str:
    nonce = os.urandom(settings.NONCE_SIZE)

    ciphertext = _master_cipher(settings.ENCRYPTION_KEY_VERSION).encrypt(
        nonce,
        data_key,
        settings.KEY_INFO.encode(),
    )

    return base64.b64encode(nonce + ciphertext).decode()


def unwrap_data_key(wrapped_key: str, key_version: int) -> bytes:
    raw = base64.b64decode(wrapped_key, validate=True)

    if len(raw) <= settings.NONCE_SIZE:
        raise ValueError("invalid wrapped data key")

    return _master_cipher(key_version).decrypt(
        raw[: settings.NONCE_SIZE],
        raw[settings.NONCE_SIZE :],
        settings.KEY_INFO.encode(),
    )


def _aad(project_id: str, environment_id: str, name: str, key_version: int) -> bytes:
    return json.dumps(
        [project_id, environment_id, name, key_version],
        separators=(",", ":"),
    ).encode()


def encrypt_value(
    value: str | int | bool,
    data_key: bytes,
    project_id: str,
    environment_id: str,
    name: str,
    key_version: int,
) -> str:
    nonce = os.urandom(settings.NONCE_SIZE)
    plaintext = json.dumps(value).encode()

    ciphertext = AESGCM(data_key).encrypt(
        nonce,
        plaintext,
        _aad(project_id, environment_id, name, key_version),
    )

    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_value(
    blob: str,
    data_key: bytes,
    project_id: str,
    environment_id: str,
    name: str,
    key_version: int,
) -> str | int | bool:
    raw = base64.b64decode(blob, validate=True)

    if len(raw) <= settings.NONCE_SIZE:
        raise ValueError("invalid encrypted value")

    plaintext = AESGCM(data_key).decrypt(
        raw[: settings.NONCE_SIZE],
        raw[settings.NONCE_SIZE :],
        _aad(project_id, environment_id, name, key_version),
    )

    value: str | int | bool = json.loads(plaintext)
    return value
