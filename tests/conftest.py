import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.db.mongo as mongo_mod
import app.db.redis as redis_mod
from app.main import app


@pytest_asyncio.fixture
async def client():
    """Fresh in-memory Mongo + Redis per test, wired into the real app."""
    mongo_mod._client = AsyncMongoMockClient()
    await mongo_mod.ensure_indexes()
    redis_mod._redis = fake_aioredis.FakeRedis(decode_responses=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await redis_mod._redis.aclose()
    mongo_mod._client = None
    redis_mod._redis = None


@pytest.fixture
def register_user(client):
    async def _register(
        email: str = "user@example.com",
        name: str = "Test User",
        password: str = "password123",
    ) -> dict:
        res = await client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": password},
        )
        assert res.status_code == 201, res.text
        return res.json()

    return _register
