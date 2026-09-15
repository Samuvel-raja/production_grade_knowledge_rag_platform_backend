from dataclasses import dataclass

from app.rag.embeddings.base import Embedder
from app.rag.embeddings.compatible_embedder import CompatibleEmbedder

# Providers with an actual way to embed text. Groq has no embeddings endpoint
# at all — a user on it falls back to the server-wide embedder (see
# app.rag.embeddings). OpenRouter has no embeddings endpoint of its own
# either, but it proxies OpenAI's models under OpenAI's own names — so an
# OpenRouter user's *own* key/credits can still embed, via OpenRouter, using
# OpenAI's embedding model.
#
# IMPORTANT: a Pinecone index has one fixed vector dimension. Every document a
# workspace has already indexed was embedded with *some* provider/model; a user
# whose queries embed with a different one will get dimension-mismatch errors,
# or — if dimensions happen to coincide — silently wrong (empty) results, since
# different providers' embeddings aren't points in a comparable space. Picking
# a different provider here doesn't retroactively re-embed existing documents.


@dataclass(frozen=True)
class EmbeddingProviderInfo:
    label: str
    base_url: str | None
    default_model: str


EMBEDDING_PROVIDERS: dict[str, EmbeddingProviderInfo] = {
    "openai": EmbeddingProviderInfo("OpenAI", None, "text-embedding-3-small"),
    "gemini": EmbeddingProviderInfo(
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini-embedding-001",
    ),
    "openrouter": EmbeddingProviderInfo(
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "openai/text-embedding-3-small",
    ),
}


def supports_embeddings(provider: str) -> bool:
    return provider in EMBEDDING_PROVIDERS


def build_embedder(
    *, provider: str, api_key: str, model: str | None = None, dimensions: int | None = None
) -> Embedder:
    info = EMBEDDING_PROVIDERS[provider]
    return CompatibleEmbedder(
        api_key=api_key,
        model=model or info.default_model,
        base_url=info.base_url,
        dimensions=dimensions,
    )
