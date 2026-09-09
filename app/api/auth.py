from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import UserDoc
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.services.auth_service import authenticate_user, register_user

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
