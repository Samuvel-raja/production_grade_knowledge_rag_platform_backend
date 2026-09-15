from dataclasses import dataclass
from typing import Any, Protocol

from app.services.ingestion.loaders import Block


@dataclass
class Chunk:
    text: str
    chunk_index: int
    page: int | None
    section: str | None
    token_count: int


class Chunker(Protocol):
    def split(self, blocks: list[Block], doc_meta: dict[str, Any]) -> list[Chunk]: ...
