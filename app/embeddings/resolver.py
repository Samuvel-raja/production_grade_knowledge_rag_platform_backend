from app.core.config import settings
from app.core.crypto import decrypt
from app.embeddings import get_embedder
from app.embeddings.base import Embedder
from app.embeddings.providers import build_embedder, supports_embeddings
from app.models.user import UserDoc


async def get_embedder_for_user(user: UserDoc | None) -> Embedder | None:
    """A user's own LLM provider embeds their queries too, if that provider
    supports embeddings (openai, gemini, openrouter — via OpenAI's model). Groq
    users, and documents with no known uploader, fall back to the server-wide
    default embedder. Returns None if nothing is configured anywhere.

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
