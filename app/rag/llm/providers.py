from dataclasses import dataclass

from app.rag.llm.base import LLM
from app.rag.llm.compatible_llm import CompatibleLLM

# OpenAI, Groq and OpenRouter all speak the OpenAI chat-completions wire format
# natively; Google exposes the same format for Gemini via its OpenAI-compat
# endpoint. So one client class covers all four providers — only base_url and
# the default model differ. Swap in a native SDK later if a provider needs
# something the compat layer can't do (e.g. Gemini-specific features).


@dataclass(frozen=True)
class ProviderInfo:
    label: str
    base_url: str | None
    default_model: str


PROVIDERS: dict[str, ProviderInfo] = {
    "openai": ProviderInfo("OpenAI", None, "gpt-4o-mini"),
    "gemini": ProviderInfo(
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini-3.6-flash",
    ),
    "openrouter": ProviderInfo(
        "OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"
    ),
    "groq": ProviderInfo(
        "Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"
    ),
}


def is_supported_provider(provider: str) -> bool:
    return provider in PROVIDERS


def default_model_for(provider: str) -> str:
    return PROVIDERS[provider].default_model


def build_llm(*, provider: str, api_key: str, model: str | None = None) -> LLM:
    info = PROVIDERS[provider]
    return CompatibleLLM(api_key=api_key, model=model or info.default_model, base_url=info.base_url)
