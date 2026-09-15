from dataclasses import dataclass

from app.services.rag.retrieval import RetrievedChunk


@dataclass
class Citation:
    index: int
    document_id: str
    document_name: str
    page: int | None
    section: str | None
    chunk_id: str


def build_context(chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    """Number each chunk as a source the LLM can cite, and return the matching
    citation list. Every chunk that's given to the LLM is returned as a citation —
    validating that a *used* citation actually appears in the answer is Phase 7."""
    blocks: list[str] = []
    citations: list[Citation] = []

    for i, chunk in enumerate(chunks, start=1):
        location = ""
        if chunk.page is not None:
            location += f" — page {chunk.page}"
        if chunk.section:
            location += f" — {chunk.section}"
        blocks.append(f"[{i}] {chunk.document_name}{location}\n{chunk.text}")
        citations.append(
            Citation(
                index=i,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page=chunk.page,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
            )
        )

    return "\n\n".join(blocks), citations
