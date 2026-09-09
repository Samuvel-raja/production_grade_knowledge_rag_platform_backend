from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings
from app.core.logging import log

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue_process_document(document_id: str) -> bool:
    """Best-effort enqueue. Job id = document id, so a duplicate is dropped by arq.

    Returns False (and leaves the document at status 'uploaded') if the queue is
    unreachable — the worker can be pointed at it later.
    """
    try:
        pool = await get_pool()
        await pool.enqueue_job(
            "process_document", document_id, _job_id=f"process:{document_id}"
        )
        return True
    except Exception as exc:  # noqa: BLE001 - queue outage must not fail the upload
        log.warning("enqueue_failed", document_id=document_id, error=str(exc))
        return False


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
