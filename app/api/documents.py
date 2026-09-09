import json

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import authorize_document, authorize_workspace
from app.core.config import settings
from app.core.errors import AppError, BadRequestError
from app.models.document import DocumentDoc
from app.models.workspace import WorkspaceDoc
from app.schemas.document import DocumentOut
from app.services.ingestion.document_service import (
    create_document,
    delete_document,
    list_documents,
)
from app.workers.queue import enqueue_process_document

router = APIRouter(tags=["documents"])


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequestError("metadata must be valid JSON", code="invalid_metadata") from exc
    if not isinstance(value, dict):
        raise BadRequestError("metadata must be a JSON object", code="invalid_metadata")
    return value


@router.post(
    "/api/workspaces/{workspace_id}/documents",
    response_model=DocumentOut,
    status_code=202,
)
async def upload_document(
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    workspace: WorkspaceDoc = Depends(authorize_workspace),
) -> DocumentOut:
    meta = _parse_metadata(metadata)

    if file.size is not None and file.size > settings.max_upload_bytes:
        raise AppError(
            f"File too large (max {settings.max_upload_mb} MB)",
            code="file_too_large",
            status_code=413,
        )

    data = await file.read()
    doc = await create_document(
        workspace_id=workspace.id,
        filename=file.filename or "upload",
        data=data,
        metadata=meta,
        max_bytes=settings.max_upload_bytes,
    )
    await enqueue_process_document(doc.id)
    return DocumentOut.of(doc)


@router.get(
    "/api/workspaces/{workspace_id}/documents",
    response_model=list[DocumentOut],
)
async def list_workspace_documents(
    status: str | None = None,
    workspace: WorkspaceDoc = Depends(authorize_workspace),
) -> list[DocumentOut]:
    return [DocumentOut.of(d) for d in await list_documents(workspace.id, status)]


@router.get("/api/documents/{document_id}", response_model=DocumentOut)
async def get_one_document(doc: DocumentDoc = Depends(authorize_document)) -> DocumentOut:
    return DocumentOut.of(doc)


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_one_document(doc: DocumentDoc = Depends(authorize_document)) -> None:
    await delete_document(doc)
