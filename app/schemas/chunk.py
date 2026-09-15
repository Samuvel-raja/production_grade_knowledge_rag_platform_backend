from pydantic import BaseModel


class ChunkPreview(BaseModel):
    id: str
    chunk_index: int
    page: int | None = None
    section: str | None = None
    text: str


class ChunkListOut(BaseModel):
    chunks: list[ChunkPreview]
