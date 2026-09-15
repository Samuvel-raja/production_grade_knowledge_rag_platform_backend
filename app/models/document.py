from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import PyObjectId

DocStatus = Literal["uploaded", "processing", "processed", "failed"]
FileType = Literal["pdf", "docx", "txt", "md"]


class DocumentDoc(BaseModel):
    """Shape of a document in the `documents` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    workspace_id: PyObjectId
    filename: str                       # sanitized, stored name
    original_file_name: str             # as uploaded
    file_type: FileType
    file_size: int
    # Who uploaded it — used at ingestion time to embed with *their* configured
    # provider (see app.rag.embeddings). None for documents uploaded before
    # this existed; those fall back to the server-wide embedder.
    uploaded_by: PyObjectId | None = None
    page_count: int | None = None
    chunk_count: int | None = None      # set in Phase 3
    status: DocStatus = "uploaded"
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_error: str | None = None
    created_at: datetime
    updated_at: datetime
