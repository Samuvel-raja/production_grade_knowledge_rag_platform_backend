import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.db.mongo as mongo_mod
import app.db.redis as redis_mod
import app.storage as storage_mod
from app.main import app
from app.services.ingestion.document_service import ensure_document_indexes
from tests.fakes import FakeStorage


@pytest_asyncio.fixture
async def client():
    """Fresh in-memory Mongo + Redis + object storage per test, wired into the real app."""
    mongo_mod._client = AsyncMongoMockClient()
    await mongo_mod.ensure_indexes()
    await ensure_document_indexes()
    redis_mod._redis = fake_aioredis.FakeRedis(decode_responses=True)
    storage_mod._storage = FakeStorage()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await redis_mod._redis.aclose()
    mongo_mod._client = None
    redis_mod._redis = None
    storage_mod._storage = None


@pytest.fixture
def fake_storage() -> FakeStorage:
    assert isinstance(storage_mod._storage, FakeStorage)
    return storage_mod._storage


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


@pytest.fixture
def make_workspace(client):
    async def _make(token: str, name: str = "WS") -> dict:
        res = await client.post(
            "/api/workspaces",
            json={"name": name},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201, res.text
        return res.json()

    return _make


@pytest.fixture(autouse=True)
def _no_real_queue(monkeypatch):
    """Never touch a real Redis queue in tests — record enqueues instead."""
    calls: list[str] = []

    async def _fake_enqueue(document_id: str) -> bool:
        calls.append(document_id)
        return True

    monkeypatch.setattr("app.api.documents.enqueue_process_document", _fake_enqueue)
    return calls
