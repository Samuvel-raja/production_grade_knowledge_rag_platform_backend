from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import log
from app.embeddings.base import EmbeddingError
from app.embeddings.resolver import get_embedder_for_user
from app.llm.base import LLMError
from app.llm.resolver import get_llm_for_user
from app.models.user import UserDoc
from app.services.rag.context import Citation, build_context
from app.services.rag.prompt import SYSTEM_PROMPT, build_user_prompt
from app.services.rag.retrieval import retrieve_chunks

_NO_INDEX_ANSWER = (
    "I don't have any indexed documents to answer that from yet. "
    "Upload and process a document first."
)
_NO_MATCH_ANSWER = (
    "I don't have enough information in the available documents to answer that."
)


@dataclass
class AskResult:
    answer: str
    citations: list[Citation]
    retrieved_count: int


async def answer_question(
    *,
    workspace_id: str,
    question: str,
    user: UserDoc,
    document_ids: list[str] | None = None,
) -> AskResult:
    """Baseline RAG: embed question -> vector search -> context -> LLM -> answer.

    Each stage (retrieval, context construction, generation) is its own module so
    later phases (query rewriting, hybrid search, reranking, guardrails) slot in
    without this function turning into one giant block.

    Both the embedder and the LLM are resolved per-user: their own configured
    provider/key if they have one, else the server-wide default. For the
    embedder this only matters if the provider actually offers embeddings
    (openai, gemini, openrouter) — see app.embeddings.resolver for what a
    mismatched provider does to retrieval.
    """
    if not settings.pinecone_api_key:
        raise AppError(
            "Search isn't configured for this workspace yet",
            code="rag_unavailable",
            status_code=503,
        )

    embedder = await get_embedder_for_user(user)
    if embedder is None:
        raise AppError(
            "Add an embedding-capable provider (OpenAI or Gemini) in Settings, "
            "or ask an admin to configure one",
            code="rag_unavailable",
            status_code=503,
        )

    try:
        query_vector = await embedder.embed_query(question)
    except EmbeddingError as exc:
        log.error("rag_embedding_failed", workspace_id=workspace_id, error=str(exc))
        raise AppError(
            f"Could not process the question right now: {str(exc)[:300]}",
            code="embedding_unavailable",
            status_code=503,
        ) from exc

    chunks = await retrieve_chunks(
        workspace_id, query_vector, top_k=settings.rag_top_k, document_ids=document_ids
    )
    if not chunks:
        return AskResult(answer=_NO_INDEX_ANSWER, citations=[], retrieved_count=0)

    context_text, citations = build_context(chunks)

    llm = await get_llm_for_user(user)
    if llm is None:
        raise AppError(
            "Add an LLM API key in Settings to generate answers",
            code="llm_unavailable",
            status_code=503,
        )

    try:
        answer = await llm.generate(
            system=SYSTEM_PROMPT, prompt=build_user_prompt(context_text, question)
        )
    except LLMError as exc:
        log.error("rag_generation_failed", workspace_id=workspace_id, error=str(exc))
        raise AppError(
            f"Could not generate an answer right now: {str(exc)[:300]}",
            code="llm_unavailable",
            status_code=503,
        ) from exc

    if not answer.strip():
        answer = _NO_MATCH_ANSWER

    return AskResult(answer=answer, citations=citations, retrieved_count=len(chunks))
