from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionUnavailable(Exception):
    """SECRETS_ENCRYPTION_KEY isn't configured — can't store/read a secret."""


def _fernet() -> Fernet:
    # Not cached: settings.secrets_encryption_key is read fresh every call, so a
    # test (or a future reload) that changes it takes effect immediately.
    if not settings.secrets_encryption_key:
        raise EncryptionUnavailable
    return Fernet(settings.secrets_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionUnavailable from exc
