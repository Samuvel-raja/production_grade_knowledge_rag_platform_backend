from typing import Protocol, runtime_checkable


class EmbeddingError(Exception):
    """The embedding provider failed after its own retries. Treat as transient."""


@runtime_checkable
class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...
