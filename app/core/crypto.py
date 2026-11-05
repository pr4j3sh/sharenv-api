import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

NONCE_SIZE = 12

_key = base64.b64decode(settings.ENCRYPTION_KEY, validate=True)
_aesgcm = AESGCM(_key)


def _aad(environment_id: str, name: str) -> bytes:
    return f"{environment_id}:{name}".encode()


def encrypt_value(value: str | int | bool, environment_id: str, name: str) -> str:
    nonce = os.urandom(NONCE_SIZE)
    plaintext = json.dumps(value).encode()
    ciphertext = _aesgcm.encrypt(nonce, plaintext, _aad(environment_id, name))
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_value(blob: str, environment_id: str, name: str) -> str | int | bool:
    raw = base64.b64decode(blob, validate=True)

    if len(raw) <= NONCE_SIZE:
        raise ValueError("invalid encrypted value")

    plaintext = _aesgcm.decrypt(
        raw[:NONCE_SIZE],
        raw[NONCE_SIZE:],
        _aad(environment_id, name),
    )

    return json.loads(plaintext)
