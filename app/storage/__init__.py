from app.core.config import settings
from app.core.logging import log
from app.storage.base import Storage, StorageError
from app.storage.s3 import S3Storage

_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage(
            endpoint=settings.object_storage_endpoint,
            bucket=settings.object_storage_bucket,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            region=settings.object_storage_region,
        )
    return _storage


def init_storage() -> None:
    """Construct the client and make sure the bucket exists. Best-effort at startup."""
    storage = get_storage()
    if isinstance(storage, S3Storage):
        storage.ensure_bucket()
    log.info("storage_ready", bucket=settings.object_storage_bucket)


__all__ = ["Storage", "StorageError", "S3Storage", "get_storage", "init_storage"]
