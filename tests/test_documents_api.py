import io

from pypdf import PdfWriter

from app.core.config import settings


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _upload(
    client, token, workspace_id, *, filename="handbook.pdf", content=None, metadata=None
):
    body = content if content is not None else _pdf_bytes()
    files = {"file": (filename, body, "application/pdf")}
    data = {"metadata": metadata} if metadata else None
    return await client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files=files,
        data=data,
        headers=_headers(token),
    )


async def test_upload_creates_document_and_stores_original(
    client, register_user, make_workspace, fake_storage
):
    user = await register_user(email="up@example.com")
    ws = await make_workspace(user["access_token"])

    res = await _upload(
        client, user["access_token"], ws["id"], metadata='{"department":"HR","year":2026}'
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "uploaded"
    assert body["file_type"] == "pdf"
    assert body["metadata"] == {"department": "HR", "year": 2026}
    assert len(fake_storage.objects) == 1
    stored_key = next(iter(fake_storage.objects))
    assert stored_key.startswith(f"workspaces/{ws['id']}/documents/{body['id']}/")


async def test_upload_enqueues_processing(client, register_user, make_workspace, _no_real_queue):
    user = await register_user(email="q@example.com")
    ws = await make_workspace(user["access_token"])
    res = await _upload(client, user["access_token"], ws["id"])
    assert _no_real_queue == [res.json()["id"]]


async def test_upload_rejects_unsupported_type(client, register_user, make_workspace):
    user = await register_user(email="bad@example.com")
    ws = await make_workspace(user["access_token"])
    res = await _upload(
        client, user["access_token"], ws["id"], filename="malware.exe", content=b"MZ\x90\x00"
    )
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "unsupported_file_type"


async def test_upload_rejects_oversize(client, register_user, make_workspace, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    user = await register_user(email="big@example.com")
    ws = await make_workspace(user["access_token"])
    res = await _upload(client, user["access_token"], ws["id"])
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


async def test_list_is_scoped_to_workspace(client, register_user, make_workspace):
    user = await register_user(email="scope@example.com")
    ws_a = await make_workspace(user["access_token"], "A")
    ws_b = await make_workspace(user["access_token"], "B")
    await _upload(client, user["access_token"], ws_a["id"])

    list_a = await client.get(
        f"/api/workspaces/{ws_a['id']}/documents", headers=_headers(user["access_token"])
    )
    list_b = await client.get(
        f"/api/workspaces/{ws_b['id']}/documents", headers=_headers(user["access_token"])
    )
    assert len(list_a.json()) == 1
    assert list_b.json() == []


async def test_user_cannot_read_another_users_document(client, register_user, make_workspace):
    owner = await register_user(email="owner@example.com")
    other = await register_user(email="other@example.com")
    ws = await make_workspace(owner["access_token"])
    doc = (await _upload(client, owner["access_token"], ws["id"])).json()

    res = await client.get(
        f"/api/documents/{doc['id']}", headers=_headers(other["access_token"])
    )
    assert res.status_code == 403


async def test_delete_removes_record_and_object(
    client, register_user, make_workspace, fake_storage
):
    user = await register_user(email="del@example.com")
    ws = await make_workspace(user["access_token"])
    doc = (await _upload(client, user["access_token"], ws["id"])).json()
    stored_key = next(iter(fake_storage.objects))

    res = await client.delete(
        f"/api/documents/{doc['id']}", headers=_headers(user["access_token"])
    )
    assert res.status_code == 204
    assert fake_storage.deleted == [stored_key]

    gone = await client.get(
        f"/api/documents/{doc['id']}", headers=_headers(user["access_token"])
    )
    assert gone.status_code == 404
