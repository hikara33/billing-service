import json
import uuid
from decimal import Decimal

from app.core.redis import redis_client

BALANCE_TTL = 30
ACCOUNTS_TTL = 60


def _balance_key(account_id: uuid.UUID, user_id: uuid.UUID) -> str:
  return f"cache:balance:{user_id}:{account_id}"


async def get_cached_balance(account_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
  value = await redis_client.get(_balance_key(account_id, user_id))
  return json.loads(value) if value else None


async def set_cached_balance(account_id: uuid.UUID, user_id: uuid.UUID, balance: Decimal, currency: str) -> None:
  await redis_client.setex(
    _balance_key(account_id, user_id),
    BALANCE_TTL,
    json.dumps({ "balance": str(balance), "currency": currency })
  )


async def invalidate_balance(account_id: uuid.UUID, user_id: uuid.UUID) -> None:
  await redis_client.delete(_balance_key(account_id, user_id))
