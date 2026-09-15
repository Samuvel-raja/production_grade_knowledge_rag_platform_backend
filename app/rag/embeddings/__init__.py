from app.core.config import settings
from app.core.crypto import decrypt
from app.models.user import UserDoc
from app.rag.embeddings.base import Embedder, EmbeddingError
from app.rag.embeddings.compatible_embedder import CompatibleEmbedder
from app.rag.embeddings.providers import build_embedder, supports_embeddings

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """The one server-wide default embedder, built once from
    EMBEDDING_PROVIDER/EMBEDDING_API_KEY/EMBEDDING_MODEL."""
    global _embedder
    if _embedder is None:
        _embedder = CompatibleEmbedder(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dim,
        )
    return _embedder


async def get_embedder_for_user(user: UserDoc | None) -> Embedder | None:
    """Per-request decision: a user's own LLM provider embeds their queries too,
    if that provider supports embeddings (openai, gemini, openrouter — via
    OpenAI's model). Groq users, and documents with no known uploader, fall
    back to get_embedder() above. Returns None if nothing is configured
    anywhere.

    `user` may be None — ingestion for a document with no recorded uploader
    (e.g. seeded before this feature existed) goes straight to the fallback.
    """
    config = user.llm_config if user is not None else None
    if config is not None and supports_embeddings(config.provider):
        api_key = decrypt(config.encrypted_api_key)
        return build_embedder(
            provider=config.provider, api_key=api_key, dimensions=settings.embedding_dim
        )
    if settings.embedding_api_key:
        return get_embedder()
    return None


__all__ = [
    "Embedder",
    "EmbeddingError",
    "CompatibleEmbedder",
    "get_embedder",
    "get_embedder_for_user",
]
