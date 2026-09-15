"""Document processing: extract -> normalize -> chunk -> embed -> index.

Runs synchronously, in-process, via FastAPI BackgroundTasks — no object storage,
no separate worker, no job queue. The upload request holds the file bytes in
memory and hands them straight here; nothing re-reads them from anywhere, so
there's no retry on transient failure (embedding/vector-store hiccup -> the
document goes straight to `failed`) and nothing survives an API restart
mid-processing. That trade is deliberate for now — see
plan/backend/phase-2b-storage-and-workers.md for what comes back and why.
"""

import json
from typing import Any

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.logging import log
from app.db.redis import get_redis
from app.embeddings.base import EmbeddingError
from app.embeddings.resolver import get_embedder_for_user
from app.models.document import DocumentDoc
from app.services.auth_service import get_user_by_id
from app.services.ingestion.chunking import Chunk, get_chunker
from app.services.ingestion.document_service import get_document, set_status
from app.services.ingestion.loaders import Block, LoaderError, load_document
from app.services.ingestion.normalize import normalize_blocks
from app.vectorstore import VectorItem, VectorStoreError, get_vectorstore

_BLOCKS_TTL = 3600


async def _stash_blocks(document_id: str, blocks: list[Block]) -> None:
    payload = json.dumps([{"text": b.text, "page": b.page, "section": b.section} for b in blocks])
    await get_redis().set(f"doc:{document_id}:blocks", payload, ex=_BLOCKS_TTL)


def _chunk_metadata(chunk: Chunk, doc: DocumentDoc) -> dict[str, Any]:
    text = chunk.text
    if len(text) > settings.max_chunk_metadata_chars:
        text = text[: settings.max_chunk_metadata_chars]

    meta: dict[str, Any] = {
        "workspace_id": doc.workspace_id,
        "document_id": doc.id,
        "filename": doc.original_file_name,
        "chunk_index": chunk.chunk_index,
        "text": text,
    }
    # Pinecone metadata rejects null values, so only set what's present.
    if chunk.page is not None:
        meta["page"] = chunk.page
    if chunk.section is not None:
        meta["section"] = chunk.section
    for key in ("department", "document_type"):
        value = doc.metadata.get(key)
        if isinstance(value, str) and value:
            meta[key] = value
    year = doc.metadata.get("year")
    if isinstance(year, int):
        meta["year"] = year
    return meta


async def _index_chunks(doc: DocumentDoc, blocks: list[Block]) -> int:
    """Chunk -> embed -> upsert. Returns the chunk count, 0 if skipped.

    Embeds with the uploader's own configured provider if they have one that
    supports embeddings (openai, gemini, openrouter) — falls back to the
    server-wide default otherwise. This has to match whatever the uploader (or anyone else
    querying this workspace) embeds their questions with, or retrieval breaks;
    see app.embeddings.providers for the tradeoff.
    """
    if not settings.pinecone_api_key:
        # ponytail: lets local dev work with no Pinecone configured; the
        # pipeline activates the moment PINECONE_API_KEY is set.
        log.warning(
            "vector_pipeline_skipped", document_id=doc.id, reason="missing PINECONE_API_KEY"
        )
        return 0

    uploader = await get_user_by_id(doc.uploaded_by) if doc.uploaded_by else None
    embedder = await get_embedder_for_user(uploader)
    if embedder is None:
        log.warning(
            "vector_pipeline_skipped",
            document_id=doc.id,
            reason="no embedding provider configured (uploader nor server default)",
        )
        return 0

    chunks = get_chunker().split(blocks, doc.metadata)
    if not chunks:
        return 0

    try:
        vectors = await embedder.embed([c.text for c in chunks])
    except EmbeddingError as exc:
        log.error("process_document_embedding_failed", document_id=doc.id, error=str(exc))
        raise

    store = get_vectorstore()
    await store.delete(filter={"document_id": doc.id})  # idempotent re-run
    items = [
        VectorItem(
            id=f"{doc.id}_chunk_{chunk.chunk_index}",
            values=vector,
            metadata=_chunk_metadata(chunk, doc),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    await store.upsert(items)

    return len(chunks)


async def process_document_now(document_id: str, data: bytes) -> str:
    """Extract, chunk, embed and index a document; flip status as it progresses.

    `data` is the file's bytes, held in memory since the upload request — not
    re-read from anywhere. Re-entrant: a re-run (e.g. manually re-triggered)
    overwrites the Redis stash, deletes+reinserts vectors, and refreshes
    status/chunk_count.
    """
    try:
        doc = await get_document(document_id)
    except NotFoundError:
        log.warning("process_document_missing", document_id=document_id)
        return "missing"

    if doc.status == "processed":
        return "already_processed"

    await set_status(document_id, "processing", error=None)

    try:
        blocks, page_count = load_document(doc.file_type, data)
    except LoaderError as exc:
        await set_status(document_id, "failed", error=str(exc))
        return "failed"

    blocks = normalize_blocks(blocks)
    if not blocks:
        await set_status(document_id, "failed", error="No extractable text")
        return "failed"

    try:
        await _stash_blocks(document_id, blocks)
    except Exception as exc:  # noqa: BLE001 - best-effort cache, not load-bearing
        log.warning("process_document_stash_failed", document_id=document_id, error=str(exc))

    try:
        chunk_count = await _index_chunks(doc, blocks)
    except (EmbeddingError, VectorStoreError) as exc:
        # No retry here (see module docstring) — surface it and let the user re-upload.
        await set_status(
            document_id,
            "failed",
            page_count=page_count,
            error=f"Could not index this document: {str(exc)[:300]}",
        )
        log.error("process_document_indexing_failed", document_id=document_id, error=str(exc))
        return "failed"

    await set_status(document_id, "processed", page_count=page_count, chunk_count=chunk_count)
    log.info(
        "process_document_done",
        document_id=document_id,
        blocks=len(blocks),
        page_count=page_count,
        chunk_count=chunk_count,
    )
    return "processed"
