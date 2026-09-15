from fastapi import APIRouter, Depends

from app.api.deps import authorize_workspace, get_current_user
from app.models.user import UserDoc
from app.models.workspace import WorkspaceDoc
from app.schemas.rag import AskRequest, AskResponse, CitationOut
from app.services.rag.pipeline import answer_question

router = APIRouter(tags=["search"])


@router.post("/api/workspaces/{workspace_id}/search", response_model=AskResponse)
async def search_workspace(
    body: AskRequest,
    workspace: WorkspaceDoc = Depends(authorize_workspace),
    user: UserDoc = Depends(get_current_user),
) -> AskResponse:
    result = await answer_question(
        workspace_id=workspace.id,
        question=body.question,
        user=user,
        document_ids=body.document_ids,
    )
    return AskResponse(
        answer=result.answer,
        retrieved_count=result.retrieved_count,
        citations=[CitationOut(**vars(c)) for c in result.citations],
    )
