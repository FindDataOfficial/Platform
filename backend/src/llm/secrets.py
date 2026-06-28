"""Fernet secret encryption for LLM API keys (research R4, T009).

Symmetric, authenticated encryption. Master key from AGENT_PLATFORM_SECRET_KEY.
Plaintext keys never persisted; decrypted in-backend at call time only.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from src.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().secret_key.encode()
    # ponytail: accept raw 32-byte keys by deriving a url-safe Fernet key;
    # upgrade to a KMS/argon2-derived key if multi-tenant secrets matter.
    try:
        return Fernet(key)
    except ValueError:
        import base64
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return Fernet(derived)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode()
    except InvalidToken as e:
        raise ValueError("invalid or corrupted secret ciphertext") from e
