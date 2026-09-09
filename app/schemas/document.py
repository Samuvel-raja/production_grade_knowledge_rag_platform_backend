from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.document import DocumentDoc


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    filename: str
    original_file_name: str
    file_type: str
    file_size: int
    page_count: int | None
    chunk_count: int | None
    status: str
    metadata: dict[str, Any]
    processing_error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, doc: DocumentDoc) -> "DocumentOut":
        return cls(**doc.model_dump())
