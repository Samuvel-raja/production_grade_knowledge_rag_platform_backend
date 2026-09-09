import io
import zipfile
from dataclasses import dataclass


class LoaderError(Exception):
    """The file could not be parsed. Permanent — do not retry."""


@dataclass
class Block:
    """A contiguous span of text with the provenance a citation needs."""

    text: str
    page: int | None = None
    section: str | None = None


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_pdf(data: bytes) -> tuple[list[Block], int | None]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages
    except (PdfReadError, OSError, ValueError) as exc:
        raise LoaderError("Could not read PDF") from exc

    blocks: list[Block] = []
    for index, page in enumerate(pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 - a single bad page shouldn't kill the doc
            text = ""
        if text:
            blocks.append(Block(text=text, page=index))
    return blocks, len(pages)


def load_docx(data: bytes) -> tuple[list[Block], int | None]:
    from docx import Document as DocxDocument
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = DocxDocument(io.BytesIO(data))
    except (PackageNotFoundError, KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise LoaderError("Could not read DOCX") from exc

    blocks: list[Block] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            blocks.append(Block(text="\n".join(buffer), section=section))
            buffer = []

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style else ""
        if style.startswith("heading") or style == "title":
            flush()
            section = text
        else:
            buffer.append(text)
    flush()
    return blocks, None


def load_text(data: bytes) -> tuple[list[Block], int | None]:
    text = _decode(data).strip()
    if not text:
        return [], None
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [Block(text=p) for p in paragraphs] or [Block(text=text)], None


def load_markdown(data: bytes) -> tuple[list[Block], int | None]:
    text = _decode(data)
    blocks: list[Block] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            blocks.append(Block(text="\n".join(buffer).strip(), section=section))
            buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            section = stripped.lstrip("#").strip()
        elif stripped:
            buffer.append(line)
        else:
            flush()
    flush()
    return [b for b in blocks if b.text], None


_LOADERS = {
    "pdf": load_pdf,
    "docx": load_docx,
    "txt": load_text,
    "md": load_markdown,
}


def load_document(file_type: str, data: bytes) -> tuple[list[Block], int | None]:
    loader = _LOADERS.get(file_type)
    if loader is None:
        raise LoaderError(f"No loader for file type: {file_type}")
    return loader(data)
