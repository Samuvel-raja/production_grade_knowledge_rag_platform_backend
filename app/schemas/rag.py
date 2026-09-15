from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None


class CitationOut(BaseModel):
    index: int
    document_id: str
    document_name: str
    page: int | None = None
    section: str | None = None
    chunk_id: str


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    retrieved_count: int
