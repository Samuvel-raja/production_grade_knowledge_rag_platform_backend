from app.core.config import settings
from app.core.logging import log
from app.rag.vectorstore.base import VectorItem, VectorStore, VectorStoreError
from app.rag.vectorstore.pinecone_store import PineconeStore

_store: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    global _store
    if _store is None:
        _store = PineconeStore(
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index,
            dimension=settings.embedding_dim,
            cloud=settings.pinecone_cloud,
            region=settings.pinecone_region,
        )
    return _store


def init_vectorstore() -> None:
    """Create the index if missing. Best-effort — skipped entirely with no API key."""
    if not settings.pinecone_api_key:
        log.info("vectorstore_skipped", reason="no PINECONE_API_KEY configured")
        return
    store = get_vectorstore()
    if isinstance(store, PineconeStore):
        store.ensure_index()
    log.info("vectorstore_ready", index=settings.pinecone_index)


__all__ = [
    "VectorItem",
    "VectorStore",
    "VectorStoreError",
    "PineconeStore",
    "get_vectorstore",
    "init_vectorstore",
]
