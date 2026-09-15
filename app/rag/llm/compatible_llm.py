from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.rag.llm.base import LLMError


class CompatibleLLM:
    """LLM for any provider that speaks the OpenAI chat-completions wire format —
    OpenAI, Groq, OpenRouter natively, and Gemini via its OpenAI-compatibility
    endpoint. Only `base_url`/model differ; see app.rag.llm.providers.

    Swappable: any class implementing `LLM` (e.g. a provider with its own
    non-compatible API) can replace this behind `get_llm()` — nothing else in
    the RAG pipeline changes.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        client: Any = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def generate(self, *, system: str, prompt: str) -> str:
        try:
            response = await self._call(system, prompt)
        except Exception as exc:  # noqa: BLE001 - all treated as transient, retried above
            raise LLMError(str(exc)) from exc
        return response.choices[0].message.content or ""

    # ponytail: retries every failure the same way instead of matching OpenAI's
    # exception hierarchy exactly. Same trade-off as CompatibleEmbedder.
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    )
    async def _call(self, system: str, prompt: str):
        return await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
