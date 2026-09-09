from app.storage.base import StorageError


class FakeStorage:
    """In-memory Storage implementation for tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_get: bool = False  # flip to simulate a transient read failure

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        if self.fail_get:
            raise StorageError("simulated outage")
        try:
            return self.objects[key]
        except KeyError as exc:
            raise StorageError(f"missing key: {key}") from exc

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)

    def presigned_get_url(self, key: str, expires: int = 3600) -> str:
        return f"https://fake.local/{key}?exp={expires}"
