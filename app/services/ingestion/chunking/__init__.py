from app.core.config import settings
from app.services.ingestion.chunking.base import Chunk, Chunker
from app.services.ingestion.chunking.structural import StructuralChunker


def get_chunker() -> Chunker:
    """Strategy is swappable via CHUNK_STRATEGY; only 'structural' exists so far."""
    return StructuralChunker(
        target_tokens=settings.chunk_target_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )


__all__ = ["Chunk", "Chunker", "StructuralChunker", "get_chunker"]
