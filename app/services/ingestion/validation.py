from typing import get_args

from app.core.errors import AppError, BadRequestError
from app.models.document import FileType

ALLOWED_EXT: set[str] = set(get_args(FileType))

# Magic bytes for the container formats we can cheaply verify.
_MAGIC = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # docx is a zip archive
}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_upload(filename: str, data: bytes, max_bytes: int) -> tuple[FileType, int]:
    """Return (file_type, size) or raise an AppError with a client-safe code."""
    ext = _extension(filename)
    if ext not in ALLOWED_EXT:
        raise AppError(
            "Unsupported file type. Allowed: PDF, DOCX, TXT, MD.",
            code="unsupported_file_type",
            status_code=415,
        )

    size = len(data)
    if size == 0:
        raise BadRequestError("File is empty", code="empty_file")
    if size > max_bytes:
        raise AppError(
            f"File too large (max {max_bytes // (1024 * 1024)} MB)",
            code="file_too_large",
            status_code=413,
        )

    magic = _MAGIC.get(ext)
    if magic and not data.startswith(magic):
        raise BadRequestError(
            "File content does not match its extension",
            code="file_type_mismatch",
        )

    return ext, size  # type: ignore[return-value]
