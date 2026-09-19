import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@test.com",
        "password": "pass12345678",
        "full_name": "Test User"
    })
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["email"] == "test@test.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = { "email": "dup@test.com", "password": "pass12345678", "full_name": "test" }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@test.com",
        "password": "pass12345678",
        "full_name": "Test User"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@test.com",
        "password": "pass12345678"
    })
    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert data["access_token"]
    assert data.get("token_type") == "bearer"

    assert "refresh_token"not in data

    assert "refresh_token" in response.cookies
    assert response.cookies["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_pass(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@test.com",
        "password": "pass12345678",
        "full_name": "Test User"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrong@test.com",
        "password": "wrongpass"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "any-password",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me(auth_client: AsyncClient):
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@test.com"


@pytest.mark.asyncio
async def test_unauthorized_me(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh(auth_client: AsyncClient):
    email = "test@test.com"

    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["access_token"]
    assert data.get("token_type") == "bearer"

    assert "refresh_token" not in data
    assert "refresh_token" in response.cookies
    assert response.cookies["refresh_token"]

    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie

    response_me = await auth_client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {data['access_token']}"
    })
    assert response_me.status_code == 200
    assert response_me.json()["email"] == email


@pytest.mark.asyncio
async def test_rotation(auth_client: AsyncClient):
    old_refresh_token = auth_client.cookies["refresh_token"]

    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 200

    new_refresh_token = response.cookies["refresh_token"]
    assert old_refresh_token != new_refresh_token

    response.cookies.clear()

    reuse_response = await auth_client.post(
        "/api/v1/auth/refresh",
        cookies={ "refresh_token": old_refresh_token }
    )
    assert reuse_response.status_code == 401
