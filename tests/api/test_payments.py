import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.models import Account


async def _set_balance(db: AsyncSession, account_id: str, amount: Decimal):
    account = await db.get(Account, account_id)
    account.balance = amount
    await db.commit()


@pytest.mark.asyncio
async def test_transfer(auth_client: AsyncClient, account: dict, db: AsyncSession):
    await auth_client.post("/api/v1/auth/register", json={
        "email": "receiver@test.com",
        "password": "password123",
        "full_name": "Receiver",
    })
    r = await auth_client.post("/api/v1/auth/login", json={
        "email": "receiver@test.com",
        "password": "password123",
    })
    token2 = r.json()["access_token"]

    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token2}"},
    ) as client2:
        r2 = await client2.post("/api/v1/accounts/", json={"currency": "RUB"})
        to_account = r2.json()

    await _set_balance(db, account["id"], Decimal("1000"))

    response = await auth_client.post("/api/v1/payments/transfer", json={
        "from_account_id": account["id"],
        "to_account_number": to_account["account_number"],
        "amount": "500",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_transfer_insufficient_funds(
    auth_client: AsyncClient, account: dict, db: AsyncSession
):
    await _set_balance(db, account["id"], Decimal("100"))

    r = await auth_client.post("/api/v1/accounts/", json={"currency": "RUB"})
    to_account = r.json()

    response = await auth_client.post("/api/v1/payments/transfer", json={
        "from_account_id": account["id"],
        "to_account_number": to_account["account_number"],
        "amount": "500",
    })
    assert response.status_code == 400
    assert "средств" in response.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_idempotency(
    auth_client: AsyncClient, account: dict, db: AsyncSession
):
    await _set_balance(db, account["id"], Decimal("1000"))

    r = await auth_client.post("/api/v1/accounts/", json={"currency": "RUB"})
    to_account = r.json()

    idempotency_key = "test-key-123"

    r1 = await auth_client.post(
        "/api/v1/payments/transfer",
        json={
            "from_account_id": account["id"],
            "to_account_number": to_account["account_number"],
            "amount": "300",
        },
        headers={"X-Idempotency-Key": idempotency_key},
    )
    r2 = await auth_client.post(
        "/api/v1/payments/transfer",
        json={
            "from_account_id": account["id"],
            "to_account_number": to_account["account_number"],
            "amount": "300",
        },
        headers={"X-Idempotency-Key": idempotency_key},
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    balance = await auth_client.get(f"/api/v1/accounts/{account['id']}/balance")
    assert Decimal(balance.json()["balance"]) == Decimal("700")


@pytest.mark.asyncio
async def test_transfer_same_account(auth_client: AsyncClient, account: dict):
    response = await auth_client.post("/api/v1/payments/transfer", json={
        "from_account_id": account["id"],
        "to_account_number": account["account_number"],
        "amount": "100",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_history(auth_client: AsyncClient, account: dict, db: AsyncSession):
    await _set_balance(db, account["id"], Decimal("1000"))

    r = await auth_client.post("/api/v1/accounts/", json={"currency": "RUB"})
    to_account = r.json()

    await auth_client.post("/api/v1/payments/transfer", json={
        "from_account_id": account["id"],
        "to_account_number": to_account["account_number"],
        "amount": "100",
    })

    response = await auth_client.get(f"/api/v1/payments/history/{account['id']}")
    assert response.status_code == 200
    assert response.json()["total"] >= 1