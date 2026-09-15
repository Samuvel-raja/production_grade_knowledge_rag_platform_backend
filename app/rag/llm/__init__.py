from app.core.config import settings
from app.rag.llm.base import LLM, LLMError
from app.rag.llm.compatible_llm import CompatibleLLM
from app.rag.llm.providers import PROVIDERS, build_llm, default_model_for, is_supported_provider

_llm: LLM | None = None


def get_llm() -> LLM:
    """Server-wide default LLM, built from LLM_PROVIDER/LLM_API_KEY/LLM_MODEL.
    Per-workspace overrides are resolved separately — see app.rag.llm.resolver."""
    global _llm
    if _llm is None:
        _llm = build_llm(
            provider=settings.llm_provider, api_key=settings.llm_api_key, model=settings.llm_model
        )
    return _llm


__all__ = [
    "LLM",
    "LLMError",
    "CompatibleLLM",
    "PROVIDERS",
    "build_llm",
    "default_model_for",
    "is_supported_provider",
    "get_llm",
]
