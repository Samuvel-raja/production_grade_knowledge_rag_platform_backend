import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.errors import AppError, BadRequestError, NotFoundError
from app.core.logging import log
from app.db.mongo import get_db
from app.models.document import DocStatus, DocumentDoc
from app.services.ingestion.validation import validate_upload
from app.storage import StorageError, get_storage

_CONTENT_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
}
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
) -> DocumentDoc:
    file_type, size = validate_upload(filename, data, max_bytes)

    doc_id = ObjectId()
    stored_name = _sanitize(filename)
    storage_key = f"workspaces/{workspace_id}/documents/{doc_id}/{stored_name}"

    # Store the original first — only create the record once the bytes are safe.
    try:
        await get_storage().put(storage_key, data, _CONTENT_TYPE[file_type])
    except StorageError as exc:
        log.error("storage_put_failed", storage_key=storage_key, error=str(exc))
        raise AppError(
            "Storage is temporarily unavailable", code="storage_unavailable", status_code=503
        ) from exc

    now = datetime.now(UTC)
    record = {
        "_id": doc_id,
        "workspace_id": ObjectId(workspace_id),
        "filename": stored_name,
        "original_file_name": filename,
        "storage_key": storage_key,
        "file_type": file_type,
        "file_size": size,
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
    try:
        await get_storage().delete(doc.storage_key)
    except StorageError as exc:  # object may already be gone; don't block the record delete
        log.warning("storage_delete_failed", storage_key=doc.storage_key, error=str(exc))
    await get_db().documents.delete_one({"_id": ObjectId(doc.id)})
    # Phase 3: also delete vectors where metadata.document_id == doc.id


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
