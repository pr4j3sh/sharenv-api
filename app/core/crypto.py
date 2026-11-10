import base64
import hashlib
import hmac
import json
import os
import secrets
import string

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def generate_otp() -> str:
    length = settings.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    # HMAC keyed with JWT_SECRET acts as a server-side pepper: a database-only
    # attacker cannot verify guesses for the stored hash offline.
    return hmac.new(
        settings.JWT_SECRET.encode(), otp.encode(), hashlib.sha256
    ).hexdigest()


def verify_otp(stored_hash: str, otp: str) -> bool:
    return secrets.compare_digest(stored_hash, hash_otp(otp))


def get_master_key() -> bytes:
    return base64.b64decode(settings.ENCRYPTION_KEY, validate=True)


def get_data_key() -> bytes:
    return secrets.token_bytes(settings.TOKEN_BYTES)


def wrap_data_key(data_key: bytes) -> str:
    master_key = get_master_key()
    nonce = os.urandom(settings.NONCE_SIZE)

    ciphertext = AESGCM(master_key).encrypt(
        nonce,
        data_key,
        settings.KEY_INFO.encode(),
    )

    return base64.b64encode(nonce + ciphertext).decode()


def unwrap_data_key(wrapped_key: str) -> bytes:
    master_key = get_master_key()
    raw = base64.b64decode(wrapped_key, validate=True)

    if len(raw) <= settings.NONCE_SIZE:
        raise ValueError("invalid wrapped data key")

    return AESGCM(master_key).decrypt(
        raw[: settings.NONCE_SIZE],
        raw[settings.NONCE_SIZE :],
        settings.KEY_INFO.encode(),
    )


def _aad(environment_id: str, name: str) -> bytes:
    return f"{environment_id}:{name}".encode()


def encrypt_value(
    value: str | int | bool,
    data_key: bytes,
    environment_id: str,
    name: str,
) -> str:
    nonce = os.urandom(settings.NONCE_SIZE)
    plaintext = json.dumps(value).encode()

    ciphertext = AESGCM(data_key).encrypt(
        nonce,
        plaintext,
        _aad(environment_id, name),
    )

    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_value(
    blob: str,
    data_key: bytes,
    environment_id: str,
    name: str,
) -> str | int | bool:
    raw = base64.b64decode(blob, validate=True)

    if len(raw) <= settings.NONCE_SIZE:
        raise ValueError("invalid encrypted value")

    plaintext = AESGCM(data_key).decrypt(
        raw[: settings.NONCE_SIZE],
        raw[settings.NONCE_SIZE :],
        _aad(environment_id, name),
    )

    return json.loads(plaintext)
