import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.logging import log


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.token_encryption_key
    if not key:
        # Dev/test convenience only. Production must set TOKEN_ENCRYPTION_KEY.
        log.warning("token_encryption_key_missing_using_derived_dev_key")
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str | None:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None
