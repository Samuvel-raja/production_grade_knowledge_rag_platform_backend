async def test_register_returns_token_and_hides_hash(client):
    res = await client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password123"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert "password_hash" not in body["user"]


async def test_register_duplicate_email_conflicts(client, register_user):
    await register_user(email="dup@example.com")
    res = await client.post(
        "/api/auth/register",
        json={"name": "Other", "email": "dup@example.com", "password": "password123"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


async def test_register_weak_password_rejected(client):
    res = await client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "weak@example.com", "password": "short"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


async def test_login_success(client, register_user):
    await register_user(email="log@example.com", password="password123")
    res = await client.post(
        "/api/auth/login",
        json={"email": "log@example.com", "password": "password123"},
    )
    assert res.status_code == 200
    assert res.json()["access_token"]


async def test_login_wrong_password(client, register_user):
    await register_user(email="log2@example.com", password="password123")
    res = await client.post(
        "/api/auth/login",
        json={"email": "log2@example.com", "password": "wrongpass"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


async def test_me_with_token(client, register_user):
    reg = await register_user(email="me@example.com")
    res = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {reg['access_token']}"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


async def test_me_without_token(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


async def test_me_with_garbage_token(client):
    res = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401
