import pytest


@pytest.fixture
def auth_headers():
    def _headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return _headers


async def test_create_requires_auth(client):
    res = await client.post("/api/workspaces", json={"name": "HR"})
    assert res.status_code == 401


async def test_create_sets_owner_and_member(client, register_user, auth_headers):
    reg = await register_user(email="owner@example.com")
    res = await client.post(
        "/api/workspaces",
        json={"name": "HR"},
        headers=auth_headers(reg["access_token"]),
    )
    assert res.status_code == 201
    ws = res.json()
    assert ws["name"] == "HR"
    assert ws["owner_id"] == reg["user"]["id"]
    assert ws["member_ids"] == [reg["user"]["id"]]


async def test_list_scoped_to_caller(client, register_user, auth_headers):
    a = await register_user(email="a@example.com")
    b = await register_user(email="b@example.com")
    await client.post(
        "/api/workspaces", json={"name": "A-space"}, headers=auth_headers(a["access_token"])
    )

    res_a = await client.get("/api/workspaces", headers=auth_headers(a["access_token"]))
    res_b = await client.get("/api/workspaces", headers=auth_headers(b["access_token"]))

    assert [w["name"] for w in res_a.json()] == ["A-space"]
    assert res_b.json() == []


async def test_user_cannot_read_other_users_workspace(client, register_user, auth_headers):
    a = await register_user(email="a2@example.com")
    b = await register_user(email="b2@example.com")
    created = await client.post(
        "/api/workspaces", json={"name": "Private"}, headers=auth_headers(a["access_token"])
    )
    ws_id = created.json()["id"]

    res = await client.get(
        f"/api/workspaces/{ws_id}", headers=auth_headers(b["access_token"])
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "not_a_member"


async def test_get_missing_workspace_404(client, register_user, auth_headers):
    a = await register_user(email="a3@example.com")
    res = await client.get(
        "/api/workspaces/507f1f77bcf86cd799439011", headers=auth_headers(a["access_token"])
    )
    assert res.status_code == 404


async def test_get_malformed_id_400(client, register_user, auth_headers):
    a = await register_user(email="a4@example.com")
    res = await client.get(
        "/api/workspaces/not-an-objectid", headers=auth_headers(a["access_token"])
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_id"
