import json

from arq import Retry

from app.core.errors import NotFoundError
from app.core.logging import log
from app.db.redis import get_redis
from app.services.ingestion.document_service import get_document, set_status
from app.services.ingestion.loaders import Block, LoaderError, load_document
from app.services.ingestion.normalize import normalize_blocks
from app.storage import StorageError, get_storage

_BLOCKS_TTL = 3600


async def _stash_blocks(document_id: str, blocks: list[Block]) -> None:
    payload = json.dumps(
        [{"text": b.text, "page": b.page, "section": b.section} for b in blocks]
    )
    await get_redis().set(f"doc:{document_id}:blocks", payload, ex=_BLOCKS_TTL)


async def process_document(ctx: dict, document_id: str) -> str:
    """Extract + normalize text, stash blocks for Phase 3, flip status.

    Re-entrant: a re-run overwrites the stash and status. Chunking/embeddings
    happen in Phase 3.
    """
    try:
        doc = await get_document(document_id)
    except NotFoundError:
        log.warning("process_document_missing", document_id=document_id)
        return "missing"

    if doc.status == "processed":
        return "already_processed"

    await set_status(document_id, "processing", error=None)

    # Storage read — transient failures get retried by arq.
    try:
        data = await get_storage().get(doc.storage_key)
    except StorageError as exc:
        log.warning("process_document_storage_retry", document_id=document_id, error=str(exc))
        raise Retry(defer=ctx.get("job_try", 1) * 5) from exc

    # Parsing — permanent failures, do not retry.
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
    except Exception as exc:  # noqa: BLE001 - Phase 3 re-extracts from storage if this is lost
        log.warning("process_document_stash_failed", document_id=document_id, error=str(exc))

    await set_status(document_id, "processed", page_count=page_count)
    log.info(
        "process_document_done",
        document_id=document_id,
        blocks=len(blocks),
        page_count=page_count,
    )
    return "processed"
