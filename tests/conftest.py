import os
from dotenv import load_dotenv
load_dotenv(".env.test", override=False)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

test_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
)

TestFactorySession = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def redis(monkeypatch):
    client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    await client.flushdb()

    monkeypatch.setattr(
        "app.core.rate_limiter.redis_client",
        client,
    )

    yield client

    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def db():
    async with TestFactorySession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db, monkeypatch):
    async def fake_rate_limit(*args, **kwargs):
        pass

    monkeypatch.setattr(
        "app.api.v1.auth.check_register_rate_limit",
        fake_rate_limit,
    )

    monkeypatch.setattr(
        "app.api.v1.auth.check_login_rate_limit",
        fake_rate_limit,
    )

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@test.com",
            "password": "test12345678",
            "full_name": "Test User",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@test.com",
            "password": "test12345678",
        },
    )

    token = response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest_asyncio.fixture
async def account(auth_client):
    response = await auth_client.post(
        "/api/v1/accounts/",
        json={"currency": "RUB"},
    )

    return response.json()