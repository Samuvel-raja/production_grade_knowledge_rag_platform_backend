from fastapi import APIRouter, Depends

from app.api.deps import authorize_workspace, get_current_user
from app.models.user import UserDoc
from app.models.workspace import WorkspaceDoc
from app.schemas.workspace import CreateWorkspaceRequest, WorkspaceOut
from app.services.workspace_service import create_workspace, list_workspaces

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _to_out(workspace: WorkspaceDoc) -> WorkspaceOut:
    return WorkspaceOut(**workspace.model_dump())


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create(
    body: CreateWorkspaceRequest,
    user: UserDoc = Depends(get_current_user),
) -> WorkspaceOut:
    return _to_out(await create_workspace(body.name, user))


@router.get("", response_model=list[WorkspaceOut])
async def list_all(user: UserDoc = Depends(get_current_user)) -> list[WorkspaceOut]:
    return [_to_out(w) for w in await list_workspaces(user)]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_one(workspace: WorkspaceDoc = Depends(authorize_workspace)) -> WorkspaceOut:
    return _to_out(workspace)
