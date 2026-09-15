"""Ask each provider what models a given key can actually use, straight from
their own API — instead of us hardcoding a model name that quietly gets
deprecated (exactly what happened with gemini-2.5-flash)."""

import httpx

_TIMEOUT = 10.0

# Heuristic filter for the OpenAI-shaped /models list, which mixes chat models
# in with embeddings/audio/image/moderation models. Not perfect, but the
# common non-chat families all show up in the id.
_NON_CHAT_HINTS = (
    "embedding",
    "whisper",
    "tts",
    "dall-e",
    "moderation",
    "davinci-002",
    "babbage",
    "audio",
    "realtime",
    "transcribe",
)


class ModelCatalogError(Exception):
    """Could not reach the provider or the key was rejected."""


async def list_models(*, provider: str, api_key: str) -> list[str]:
    if provider == "openai":
        return await _list_openai_shaped(
            "https://api.openai.com/v1/models", api_key, chat_only=True
        )
    if provider == "groq":
        return await _list_openai_shaped(
            "https://api.groq.com/openai/v1/models", api_key, chat_only=False
        )
    if provider == "openrouter":
        return await _list_openai_shaped(
            "https://openrouter.ai/api/v1/models", api_key, chat_only=False
        )
    if provider == "gemini":
        return await _list_gemini(api_key)
    raise ModelCatalogError(f"Unsupported provider: {provider}")


async def _get(url: str, **kwargs) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise ModelCatalogError(
            f"{exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelCatalogError(str(exc)) from exc


async def _list_openai_shaped(url: str, api_key: str, *, chat_only: bool) -> list[str]:
    body = await _get(url, headers={"Authorization": f"Bearer {api_key}"})
    ids = [m["id"] for m in body.get("data", []) if "id" in m]
    if chat_only:
        ids = [i for i in ids if not any(hint in i.lower() for hint in _NON_CHAT_HINTS)]
    return sorted(ids)


async def _list_gemini(api_key: str) -> list[str]:
    # The native Gemini API (not the OpenAI-compat one) is what actually reports
    # which models this specific key/account can use — the compat endpoint
    # doesn't expose a models list at all.
    body = await _get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
    )
    names = []
    for model in body.get("models", []):
        if "generateContent" in model.get("supportedGenerationMethods", []):
            names.append(model.get("name", "").removeprefix("models/"))
    return sorted(n for n in names if n)
