from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, search, workspaces
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging, log
from app.db.mongo import close_mongo, connect_mongo, get_client
from app.db.redis import close_redis, connect_redis, get_redis
from app.llm.providers import PROVIDERS
from app.services.ingestion.document_service import ensure_document_indexes
from app.vectorstore import init_vectorstore


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    await connect_mongo()
    await ensure_document_indexes()
    # Redis is optional for now — only /health and a best-effort block cache use
    # it (no queue, no worker — see plan/backend/phase-2b-storage-and-workers.md).
    # Skip it if unreachable instead of blocking startup.
    try:
        await connect_redis(retries=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_unavailable_skipping", error=str(exc))
    try:
        init_vectorstore()
    except Exception as exc:  # noqa: BLE001
        log.warning("vectorstore_unavailable_skipping", error=str(exc))
    log.info("startup_complete", env=settings.app_env)
    yield
    await close_mongo()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise Knowledge Intelligence API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(workspaces.router)
    app.include_router(documents.router)
    app.include_router(search.router)

    @app.get("/api/llm-providers", tags=["meta"])
    async def llm_providers() -> list[dict]:
        return [
            {"id": pid, "label": info.label, "default_model": info.default_model}
            for pid, info in PROVIDERS.items()
        ]

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        mongo_ok = False
        redis_ok = False
        try:
            await get_client().admin.command("ping")
            mongo_ok = True
        except Exception:  # noqa: BLE001
            pass
        try:
            await get_redis().ping()
            redis_ok = True
        except Exception:  # noqa: BLE001
            pass
        return {
            "status": "ok" if (mongo_ok and redis_ok) else "degraded",
            "mongo": mongo_ok,
            "redis": redis_ok,
            "vectorstore_configured": bool(settings.pinecone_api_key),
            "embedder_configured": bool(settings.embedding_api_key),
            "llm_configured": bool(settings.llm_api_key),
        }

    return app


app = create_app()
