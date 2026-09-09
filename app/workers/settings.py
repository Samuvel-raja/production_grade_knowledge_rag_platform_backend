from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import configure_logging, log
from app.db.mongo import close_mongo, connect_mongo
from app.db.redis import close_redis, connect_redis
from app.services.ingestion.document_service import ensure_document_indexes
from app.storage import init_storage
from app.workers.tasks import process_document


async def _startup(ctx: dict) -> None:
    configure_logging()
    await connect_mongo()
    await connect_redis()
    await ensure_document_indexes()
    try:
        init_storage()
    except Exception as exc:  # noqa: BLE001
        log.warning("worker_storage_unavailable", error=str(exc))
    log.info("worker_started")


async def _shutdown(ctx: dict) -> None:
    await close_mongo()
    await close_redis()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [process_document]
    on_startup = _startup
    on_shutdown = _shutdown
    max_tries = 3
    job_timeout = 300
    keep_result = 3600
