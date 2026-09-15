from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.errors import AppError, BadRequestError
from app.core.security import create_access_token
from app.models.user import UserDoc
from app.rag.llm.model_catalog import ModelCatalogError, list_models
from app.rag.llm.providers import is_supported_provider
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.schemas.llm import ListModelsRequest, LLMConfigOut, ModelListOut, SetLLMConfigRequest
from app.services.auth_service import authenticate_user, register_user
from app.services.user_llm_service import clear_llm_config, set_llm_config

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_user_out(user: UserDoc) -> UserOut:
    return UserOut(**user.model_dump())


def _auth_response(user: UserDoc) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user.id), user=_to_user_out(user))


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest) -> AuthResponse:
    user = await register_user(body.name, body.email, body.password)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    user = await authenticate_user(body.email, body.password)
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: UserDoc = Depends(get_current_user)) -> UserOut:
    return _to_user_out(user)


def _to_llm_config_out(user: UserDoc) -> LLMConfigOut:
    if user.llm_config is None:
        return LLMConfigOut(configured=False)
    return LLMConfigOut(
        configured=True, provider=user.llm_config.provider, model=user.llm_config.model
    )


@router.get("/llm-config", response_model=LLMConfigOut)
async def get_llm_config(user: UserDoc = Depends(get_current_user)) -> LLMConfigOut:
    """Never returns the key itself — only whether one is set, and which provider/model."""
    return _to_llm_config_out(user)


@router.put("/llm-config", response_model=LLMConfigOut)
async def put_llm_config(
    body: SetLLMConfigRequest,
    user: UserDoc = Depends(get_current_user),
) -> LLMConfigOut:
    provider, model = await set_llm_config(
        user.id, provider=body.provider, api_key=body.api_key, model=body.model
    )
    return LLMConfigOut(configured=True, provider=provider, model=model)


@router.delete("/llm-config", status_code=204)
async def delete_llm_config(user: UserDoc = Depends(get_current_user)) -> None:
    await clear_llm_config(user.id)


@router.post("/llm-config/models", response_model=ModelListOut)
async def list_llm_models(
    body: ListModelsRequest,
    _user: UserDoc = Depends(get_current_user),
) -> ModelListOut:
    """Asks the provider itself which models this key can use — never stored,
    the key here is just borrowed for one lookup call."""
    if not is_supported_provider(body.provider):
        raise BadRequestError(f"Unsupported provider: {body.provider}", code="unsupported_provider")
    try:
        models = await list_models(provider=body.provider, api_key=body.api_key)
    except ModelCatalogError as exc:
        raise AppError(
            f"Could not list models for this key: {str(exc)[:300]}",
            code="model_catalog_unavailable",
            status_code=502,
        ) from exc
    return ModelListOut(models=models)
