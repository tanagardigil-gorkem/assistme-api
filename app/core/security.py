from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import get_settings

_settings = get_settings()
_fernet = Fernet(_settings.encryption_key.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a token string using Fernet."""
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token string."""
    return _fernet.decrypt(encrypted_token.encode()).decode()
