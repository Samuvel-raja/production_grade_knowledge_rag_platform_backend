from datetime import UTC, datetime

from bson import ObjectId

from app.core.config import settings
from app.core.crypto import encrypt
from app.core.errors import AppError, BadRequestError
from app.db.mongo import get_db
from app.llm.providers import default_model_for, is_supported_provider


async def set_llm_config(
    user_id: str, *, provider: str, api_key: str, model: str | None
) -> tuple[str, str]:
    """Store the user's LLM config (encrypted). Returns the resolved (provider, model)."""
    if not is_supported_provider(provider):
        raise BadRequestError(f"Unsupported provider: {provider}", code="unsupported_provider")
    if not settings.secrets_encryption_key:
        raise AppError(
            "Server isn't configured to store API keys yet",
            code="encryption_unavailable",
            status_code=503,
        )

    resolved_model = model or default_model_for(provider)
    llm_config = {
        "provider": provider,
        "model": resolved_model,
        "encrypted_api_key": encrypt(api_key),
    }
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"llm_config": llm_config, "updated_at": datetime.now(UTC)}},
    )
    return provider, resolved_model


async def clear_llm_config(user_id: str) -> None:
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$unset": {"llm_config": ""}, "$set": {"updated_at": datetime.now(UTC)}},
    )
