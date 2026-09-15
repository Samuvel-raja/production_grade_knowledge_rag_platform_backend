import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.config import settings
from app.core.errors import BadRequestError, NotFoundError
from app.core.logging import log
from app.db.mongo import get_db
from app.models.document import DocStatus, DocumentDoc
from app.rag.vectorstore import VectorStoreError, get_vectorstore
from app.services.ingestion.validation import validate_upload

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(filename: str) -> str:
    name = _SAFE_NAME.sub("_", filename.strip()) or "upload"
    return name[-200:]


async def ensure_document_indexes() -> None:
    db = get_db()
    await db.documents.create_index("workspace_id")
    await db.documents.create_index([("workspace_id", 1), ("status", 1)])


async def create_document(
    *,
    workspace_id: str,
    filename: str,
    data: bytes,
    metadata: dict[str, Any] | None,
    max_bytes: int,
    uploaded_by: str | None = None,
) -> DocumentDoc:
    """Validate and record a document. The bytes are not persisted anywhere —
    they're handed straight to background processing for this one request and
    then discarded. See plan/backend/phase-2b-storage-and-workers.md."""
    file_type, size = validate_upload(filename, data, max_bytes)

    doc_id = ObjectId()
    stored_name = _sanitize(filename)

    now = datetime.now(UTC)
    record = {
        "_id": doc_id,
        "workspace_id": ObjectId(workspace_id),
        "filename": stored_name,
        "original_file_name": filename,
        "file_type": file_type,
        "file_size": size,
        "uploaded_by": ObjectId(uploaded_by) if uploaded_by else None,
        "page_count": None,
        "chunk_count": None,
        "status": "uploaded",
        "metadata": metadata or {},
        "processing_error": None,
        "created_at": now,
        "updated_at": now,
    }
    await get_db().documents.insert_one(record)
    return DocumentDoc.model_validate(record)


async def list_documents(workspace_id: str, status: str | None = None) -> list[DocumentDoc]:
    query: dict[str, Any] = {"workspace_id": ObjectId(workspace_id)}
    if status:
        query["status"] = status
    cursor = get_db().documents.find(query).sort("created_at", -1)
    return [DocumentDoc.model_validate(row) async for row in cursor]


async def get_document(document_id: str) -> DocumentDoc:
    if not ObjectId.is_valid(document_id):
        raise BadRequestError("Invalid document id", code="invalid_id")
    row = await get_db().documents.find_one({"_id": ObjectId(document_id)})
    if row is None:
        raise NotFoundError("Document not found")
    return DocumentDoc.model_validate(row)


async def delete_document(doc: DocumentDoc) -> None:
    if settings.pinecone_api_key:
        try:
            await get_vectorstore().delete(filter={"document_id": doc.id})
        except VectorStoreError as exc:
            log.warning("vectorstore_delete_failed", document_id=doc.id, error=str(exc))
    await get_db().documents.delete_one({"_id": ObjectId(doc.id)})


async def set_status(
    document_id: str,
    status: DocStatus,
    *,
    page_count: int | None = None,
    chunk_count: int | None = None,
    error: str | None = None,
) -> None:
    patch: dict[str, Any] = {
        "status": status,
        "processing_error": error,
        "updated_at": datetime.now(UTC),
    }
    if page_count is not None:
        patch["page_count"] = page_count
    if chunk_count is not None:
        patch["chunk_count"] = chunk_count
    await get_db().documents.update_one({"_id": ObjectId(document_id)}, {"$set": patch})
