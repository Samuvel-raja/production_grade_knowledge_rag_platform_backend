from typing import Any

import anyio
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException

from app.vectorstore.base import VectorItem, VectorStoreError

_UPSERT_BATCH = 100


def _as_dict(obj: Any) -> dict:
    """Pinecone SDK responses come back as dict-like or attribute-like depending
    on version; normalize once here instead of branching at every call site."""
    return obj if isinstance(obj, dict) else obj.to_dict() if hasattr(obj, "to_dict") else vars(obj)


class PineconeStore:
    """Vector store backed by a single shared Pinecone serverless index.

    Workspace isolation is enforced by callers passing `workspace_id` in every
    query filter — this class never assumes it.

    Serverless Pinecone has no delete-by-metadata-filter, only delete-by-id or
    delete-all. Chunk ids are deterministic (`{document_id}_chunk_{n}`), so
    `delete(filter={"document_id": ...})` is implemented as: list ids by prefix,
    then delete those ids. That is the only filter shape this store supports.
    """

    def __init__(
        self,
        *,
        api_key: str,
        index_name: str,
        dimension: int,
        cloud: str,
        region: str,
    ) -> None:
        self._pc = Pinecone(api_key=api_key)
        self._index_name = index_name
        self._dimension = dimension
        self._cloud = cloud
        self._region = region
        self._index = None

    def ensure_index(self) -> None:
        existing = set(self._pc.list_indexes().names())
        if self._index_name not in existing:
            self._pc.create_index(
                name=self._index_name,
                dimension=self._dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=self._cloud, region=self._region),
            )
        self._index = self._pc.Index(self._index_name)

    def _get_index(self):
        if self._index is None:
            self._index = self._pc.Index(self._index_name)
        return self._index

    async def upsert(self, items: list[VectorItem]) -> None:
        def _do() -> None:
            index = self._get_index()
            vectors = [{"id": it.id, "values": it.values, "metadata": it.metadata} for it in items]
            for i in range(0, len(vectors), _UPSERT_BATCH):
                index.upsert(vectors=vectors[i : i + _UPSERT_BATCH])

        await self._run(_do)

    async def delete(self, *, filter: dict[str, Any]) -> None:
        document_id = filter.get("document_id")
        if document_id is None:
            raise VectorStoreError("PineconeStore.delete only supports a document_id filter")

        def _do() -> None:
            index = self._get_index()
            ids = self._list_ids(index, prefix=f"{document_id}_chunk_")
            if ids:
                index.delete(ids=ids)

        await self._run(_do)

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        def _do() -> list[dict[str, Any]]:
            index = self._get_index()
            raw = index.query(vector=vector, top_k=top_k, filter=filter, include_metadata=True)
            result = _as_dict(raw)
            return [
                {"id": m["id"], "score": m.get("score"), "metadata": m.get("metadata") or {}}
                for m in (result.get("matches") or [])
            ]

        return await self._run(_do)

    async def list_for_document(
        self, document_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        def _do() -> list[dict[str, Any]]:
            index = self._get_index()
            ids = self._list_ids(index, prefix=f"{document_id}_chunk_", limit=limit)
            if not ids:
                return []
            fetched = _as_dict(index.fetch(ids=ids))
            items = [
                {"id": vid, "metadata": _as_dict(v).get("metadata") or {}}
                for vid, v in (fetched.get("vectors") or {}).items()
            ]
            items.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
            return items

        return await self._run(_do)

    @staticmethod
    def _list_ids(index, *, prefix: str, limit: int | None = None) -> list[str]:
        ids: list[str] = []
        for page in index.list(prefix=prefix):
            ids.extend(page)
            if limit is not None and len(ids) >= limit:
                break
        return ids[:limit] if limit is not None else ids

    @staticmethod
    async def _run(fn):
        try:
            return await anyio.to_thread.run_sync(fn)
        except PineconeException as exc:
            raise VectorStoreError(str(exc)) from exc
