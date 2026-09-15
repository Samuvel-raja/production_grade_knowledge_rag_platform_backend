from app.core.config import settings
from app.rag.embeddings.base import Embedder, EmbeddingError
from app.rag.embeddings.compatible_embedder import CompatibleEmbedder

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = CompatibleEmbedder(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dim,
        )
    return _embedder


__all__ = ["Embedder", "EmbeddingError", "CompatibleEmbedder", "get_embedder"]
