from app.core.config import settings
from app.core.crypto import decrypt
from app.models.user import UserDoc
from app.rag.llm.base import LLM, LLMError
from app.rag.llm.compatible_llm import CompatibleLLM
from app.rag.llm.providers import PROVIDERS, build_llm, default_model_for, is_supported_provider

_llm: LLM | None = None


def get_llm() -> LLM:
    """The one server-wide default LLM, built once from LLM_PROVIDER/LLM_API_KEY/LLM_MODEL."""
    global _llm
    if _llm is None:
        _llm = build_llm(
            provider=settings.llm_provider, api_key=settings.llm_api_key, model=settings.llm_model
        )
    return _llm


async def get_llm_for_user(user: UserDoc) -> LLM | None:
    """Per-request decision: a user's own LLM config always wins (a fresh client
    built from their decrypted key); otherwise fall back to get_llm() above.
    Returns None if neither is configured."""
    if user.llm_config is not None:
        api_key = decrypt(user.llm_config.encrypted_api_key)
        return build_llm(
            provider=user.llm_config.provider, api_key=api_key, model=user.llm_config.model
        )
    if settings.llm_api_key:
        return get_llm()
    return None


__all__ = [
    "LLM",
    "LLMError",
    "CompatibleLLM",
    "PROVIDERS",
    "build_llm",
    "default_model_for",
    "is_supported_provider",
    "get_llm",
    "get_llm_for_user",
]
