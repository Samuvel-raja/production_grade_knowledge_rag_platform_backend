from app.core.config import settings
from app.core.crypto import decrypt
from app.models.user import UserDoc
from app.rag.llm import build_llm, get_llm
from app.rag.llm.base import LLM


async def get_llm_for_user(user: UserDoc) -> LLM | None:
    """A user's own LLM config always wins; otherwise fall back to the server
    default (LLM_API_KEY). Returns None if neither is configured."""
    if user.llm_config is not None:
        api_key = decrypt(user.llm_config.encrypted_api_key)
        return build_llm(
            provider=user.llm_config.provider, api_key=api_key, model=user.llm_config.model
        )
    if settings.llm_api_key:
        return get_llm()
    return None
