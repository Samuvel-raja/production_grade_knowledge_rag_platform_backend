from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AuthError
from app.core.security import decode_token
from app.models.document import DocumentDoc
from app.models.user import UserDoc
from app.models.workspace import WorkspaceDoc
from app.services.auth_service import get_user_by_id
from app.services.ingestion.document_service import get_document
from app.services.workspace_service import get_workspace

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserDoc:
    if credentials is None:
        raise AuthError("Not authenticated")
    subject = decode_token(credentials.credentials)
    if subject is None:
        raise AuthError("Invalid or expired token")
    user = await get_user_by_id(subject)
    if user is None:
        raise AuthError("User no longer exists")
    return user


async def authorize_workspace(
    workspace_id: str,
    user: UserDoc = Depends(get_current_user),
) -> WorkspaceDoc:
    """Resolve a path `workspace_id`, enforcing membership. Client ids are never trusted."""
    return await get_workspace(workspace_id, user)


async def authorize_document(
    document_id: str,
    user: UserDoc = Depends(get_current_user),
) -> DocumentDoc:
    """Resolve a path `document_id`, then enforce membership of its workspace."""
    doc = await get_document(document_id)
    await get_workspace(doc.workspace_id, user)  # 400 / 403 / 404
    return doc
