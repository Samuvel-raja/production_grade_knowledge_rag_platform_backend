from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.rag.embeddings.base import EmbeddingError

_BATCH_SIZE = 96


class CompatibleEmbedder:
    """Embedder for any provider that speaks the OpenAI embeddings wire format —
    OpenAI itself, Gemini (via its OpenAI-compatibility endpoint), and
    OpenRouter (proxying OpenAI's model). Only `base_url`/model differ; see
    app.rag.embeddings.providers.

    Swappable: any class implementing `Embedder` (e.g. a provider with its own
    non-compatible API) can replace this behind `get_embedder()` — nothing
    else changes.
    """

    dim = 1536

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
        dimensions: int | None = None,
        client: Any = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        # Truncates output to this many dimensions (OpenAI v3 models and Gemini's
        # gemini-embedding-001 both support it) so every provider lands vectors in
        # the shared Pinecone index's fixed dimension instead of erroring on upsert.
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            out.extend(await self._embed_batch(texts[i : i + _BATCH_SIZE]))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            response = await self._call(batch)
        except Exception as exc:  # noqa: BLE001 - network/rate-limit/etc, all treated as transient
            raise EmbeddingError(str(exc)) from exc
        return [item.embedding for item in response.data]

    # ponytail: retries every failure the same way instead of matching OpenAI's
    # exception hierarchy exactly (rate limit vs connection vs 5xx). Upgrade to
    # per-error-type handling if a real difference in behavior is needed.
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    )
    async def _call(self, batch: list[str]):
        kwargs: dict[str, Any] = {"model": self._model, "input": batch}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        return await self._client.embeddings.create(**kwargs)
