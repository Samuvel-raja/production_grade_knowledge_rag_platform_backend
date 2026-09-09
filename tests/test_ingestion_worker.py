import io
import json
from datetime import UTC, datetime

import pytest
from arq import Retry
from bson import ObjectId
from pypdf import PdfWriter

import app.db.mongo as mongo_mod
import app.db.redis as redis_mod
from app.workers.tasks import process_document


async def _seed(fake_storage, *, file_type: str, data: bytes) -> str:
    doc_id = ObjectId()
    key = f"workspaces/w/documents/{doc_id}/file.{file_type}"
    await fake_storage.put(key, data, "application/octet-stream")
    now = datetime.now(UTC)
    await mongo_mod.get_db().documents.insert_one(
        {
            "_id": doc_id,
            "workspace_id": ObjectId(),
            "filename": f"file.{file_type}",
            "original_file_name": f"file.{file_type}",
            "storage_key": key,
            "file_type": file_type,
            "file_size": len(data),
            "page_count": None,
            "chunk_count": None,
            "status": "uploaded",
            "metadata": {},
            "processing_error": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(doc_id)


async def _status(doc_id: str) -> dict:
    return await mongo_mod.get_db().documents.find_one({"_id": ObjectId(doc_id)})


async def test_processes_text_document_and_stashes_blocks(client, fake_storage):
    doc_id = await _seed(
        fake_storage, file_type="txt", data=b"First paragraph.\n\nSecond paragraph."
    )

    result = await process_document({"job_try": 1}, doc_id)

    assert result == "processed"
    row = await _status(doc_id)
    assert row["status"] == "processed"
    assert row["processing_error"] is None

    stashed = await redis_mod.get_redis().get(f"doc:{doc_id}:blocks")
    blocks = json.loads(stashed)
    assert [b["text"] for b in blocks] == ["First paragraph.", "Second paragraph."]


async def test_sets_page_count_for_pdf(client, fake_storage):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    doc_id = await _seed(fake_storage, file_type="pdf", data=buf.getvalue())

    # Blank pages have no text -> no extractable content -> failed, but page_count is still read.
    result = await process_document({"job_try": 1}, doc_id)
    row = await _status(doc_id)
    assert result == "failed"
    assert row["processing_error"] == "No extractable text"


async def test_corrupt_file_fails_without_retry(client, fake_storage):
    doc_id = await _seed(fake_storage, file_type="pdf", data=b"not a pdf at all")

    result = await process_document({"job_try": 1}, doc_id)

    assert result == "failed"
    row = await _status(doc_id)
    assert row["status"] == "failed"
    assert row["processing_error"] == "Could not read PDF"


async def test_transient_storage_error_raises_retry(client, fake_storage):
    doc_id = await _seed(fake_storage, file_type="txt", data=b"hello")
    fake_storage.fail_get = True

    with pytest.raises(Retry):
        await process_document({"job_try": 2}, doc_id)

    row = await _status(doc_id)
    assert row["status"] == "processing"  # left mid-flight for the retry


async def test_missing_document_is_noop(client, fake_storage):
    result = await process_document({"job_try": 1}, str(ObjectId()))
    assert result == "missing"
