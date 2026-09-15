from dataclasses import dataclass
from typing import Any

from app.core.errors import AppError
from app.vectorstore import VectorStoreError, get_vectorstore


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section: str | None
    text: str
    score: float


async def retrieve_chunks(
    workspace_id: str,
    query_vector: list[float],
    *,
    top_k: int,
    document_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Dense retrieval, scoped to one workspace.

    `workspace_id` is always taken from the authorized path parameter, never from
    client input — this is the one place workspace isolation is enforced for
    retrieval, so every caller goes through here rather than querying the vector
    store directly.
    """
    vector_filter: dict[str, Any] = {"workspace_id": workspace_id}
    if document_ids:
        vector_filter["document_id"] = {"$in": document_ids}

    try:
        matches = await get_vectorstore().query(query_vector, top_k=top_k, filter=vector_filter)
    except VectorStoreError as exc:
        # ponytail: string-sniffed — pinecone-client doesn't expose a typed
        # dimension-mismatch error, and this is the one case worth telling the
        # user apart from a generic outage: their embedding provider doesn't
        # match whatever indexed this workspace's documents.
        if "dimension" in str(exc).lower():
            raise AppError(
                "Your configured embedding provider doesn't match how this "
                "workspace's documents were indexed. Switch provider in "
                "Settings, or ask an admin to re-index with the same one.",
                code="embedding_mismatch",
                status_code=409,
            ) from exc
        raise AppError(
            "Search is temporarily unavailable", code="retrieval_unavailable", status_code=503
        ) from exc

    return [
        RetrievedChunk(
            chunk_id=match["id"],
            document_id=match["metadata"].get("document_id", ""),
            document_name=match["metadata"].get("filename", "Unknown document"),
            page=match["metadata"].get("page"),
            section=match["metadata"].get("section"),
            text=match["metadata"].get("text", ""),
            score=match.get("score") or 0.0,
        )
        for match in matches
    ]
