import pytest
from httpx import AsyncClient
from decimal import Decimal


@pytest.mark.asyncio
async def test_create_account(auth_client: AsyncClient):
    response = await auth_client.post("/api/v1/accounts/", json={"currency": "RUB"})
    assert response.status_code == 201
    data = response.json()
    assert data["currency"] == "RUB"
    assert Decimal(data["balance"]) == Decimal("0")
    assert "account_number" in data


@pytest.mark.asyncio
async def test_get_accounts(auth_client: AsyncClient):
    await auth_client.post("/api/v1/accounts/", json={"currency": "RUB"})
    await auth_client.post("/api/v1/accounts/", json={"currency": "USD"})
    response = await auth_client.get("/api/v1/accounts/")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_balance(auth_client: AsyncClient, account: dict):
    response = await auth_client.get(f"/api/v1/accounts/{account['id']}/balance")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["balance"]) == Decimal("0")
    assert response.json()["currency"] == "RUB"


@pytest.mark.asyncio
async def test_invalid_currency(auth_client: AsyncClient):
    response = await auth_client.post("/api/v1/accounts/", json={"currency": "GBP"})
    assert response.status_code == 422