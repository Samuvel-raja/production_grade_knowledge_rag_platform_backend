from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, workspaces
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging, log
from app.db.mongo import close_mongo, connect_mongo, get_client
from app.db.redis import close_redis, connect_redis, get_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    await connect_mongo()
    # Redis is optional for now — Phase 1 only needs it for /health. Skip it if
    # unreachable instead of blocking startup. TODO: make required once caching /
    # rate limiting land (Phase 8).
    try:
        await connect_redis(retries=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_unavailable_skipping", error=str(exc))
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
        }

    return app


app = create_app()
