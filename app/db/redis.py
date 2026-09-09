import asyncio

from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.core.config import settings
from app.core.logging import log

_redis: Redis | None = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis client not initialized")
    return _redis


async def connect_redis(retries: int = 10, delay: float = 2.0) -> None:
    global _redis
    _redis = redis_from_url(settings.redis_url, decode_responses=True)
    for attempt in range(1, retries + 1):
        try:
            await _redis.ping()
            break
        except Exception as exc:  # noqa: BLE001 - retry any connection failure
            if attempt == retries:
                raise
            log.warning("redis_connect_retry", attempt=attempt, error=str(exc))
            await asyncio.sleep(delay)
    log.info("redis_connected")


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
