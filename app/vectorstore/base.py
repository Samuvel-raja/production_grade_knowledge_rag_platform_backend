from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class VectorStoreError(Exception):
    """The vector store failed (network, timeout, unavailable). Treat as transient."""


@dataclass
class VectorItem:
    id: str
    values: list[float]
    metadata: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, items: list[VectorItem]) -> None: ...

    async def delete(self, *, filter: dict[str, Any]) -> None: ...

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def list_for_document(
        self, document_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]: ...
