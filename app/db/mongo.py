import asyncio

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import log

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB client not initialized")
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


async def connect_mongo(retries: int = 10, delay: float = 2.0) -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_dsn, serverSelectionTimeoutMS=3000)
    for attempt in range(1, retries + 1):
        try:
            await _client.admin.command("ping")
            break
        except Exception as exc:  # noqa: BLE001 - retry any connection failure
            if attempt == retries:
                raise
            log.warning("mongo_connect_retry", attempt=attempt, error=str(exc))
            await asyncio.sleep(delay)
    await ensure_indexes()
    log.info("mongo_connected", db=settings.mongodb_db)


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def ensure_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.workspaces.create_index("owner_id")
    await db.workspaces.create_index("member_ids")
