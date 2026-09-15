import re
from typing import Any

import tiktoken

from app.services.ingestion.chunking.base import Chunk
from app.services.ingestion.loaders import Block

_ENCODING = tiktoken.get_encoding("cl100k_base")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


class StructuralChunker:
    """Structure-aware chunking, not naive fixed-size splitting.

    Pass 1 (done upstream by the loaders): text is already grouped into `Block`s
    at document-structure boundaries — a PDF page, a DOCX/Markdown section, a
    text paragraph — each carrying `page`/`section` for citations.

    Pass 2 (here): each block's text is packed into ~`target_tokens` windows on
    sentence boundaries, with a ~`overlap_tokens` tail carried into the next
    window so context isn't lost at a cut. A single sentence longer than the
    target is hard-split on token boundaries as a last resort.
    """

    def __init__(self, *, target_tokens: int = 512, overlap_tokens: int = 64) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def split(self, blocks: list[Block], doc_meta: dict[str, Any] | None = None) -> list[Chunk]:
        chunks: list[Chunk] = []
        for block in blocks:
            for piece in self._split_block_text(block.text):
                chunks.append(
                    Chunk(
                        text=piece,
                        chunk_index=len(chunks),
                        page=block.page,
                        section=block.section,
                        token_count=_token_count(piece),
                    )
                )
        return chunks

    def _split_block_text(self, text: str) -> list[str]:
        sentences = [s for s in _SENTENCE_SPLIT.split(text.strip()) if s]
        if not sentences:
            return []

        pieces: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = _token_count(sentence)

            if sentence_tokens > self.target_tokens:
                if current:
                    pieces.append(" ".join(current))
                    current, current_tokens = [], 0
                pieces.extend(self._hard_split(sentence))
                continue

            if current and current_tokens + sentence_tokens > self.target_tokens:
                pieces.append(" ".join(current))
                current, current_tokens = self._overlap_tail(current)

            current.append(sentence)
            current_tokens += sentence_tokens

        if current:
            pieces.append(" ".join(current))
        return pieces

    def _overlap_tail(self, sentences: list[str]) -> tuple[list[str], int]:
        tail: list[str] = []
        tokens = 0
        for sentence in reversed(sentences):
            sentence_tokens = _token_count(sentence)
            if tail and tokens + sentence_tokens > self.overlap_tokens:
                break
            tail.insert(0, sentence)
            tokens += sentence_tokens
        return tail, tokens

    def _hard_split(self, sentence: str) -> list[str]:
        token_ids = _ENCODING.encode(sentence)
        return [
            _ENCODING.decode(token_ids[i : i + self.target_tokens])
            for i in range(0, len(token_ids), self.target_tokens)
        ]
