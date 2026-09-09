from typing import Protocol, runtime_checkable


class StorageError(Exception):
    """Transient storage failure (network, timeout, unavailable)."""


@runtime_checkable
class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def presigned_get_url(self, key: str, expires: int = 3600) -> str: ...
