from decimal import Decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, User
from app.models.models import Transaction, TransactionStatus, TransactionType
from app.schemas.accounts import AccountCreate, BalanceResponse
from app.core.cache import get_cached_balance, set_cached_balance, invalidate_balance


async def create_account(user: User, data: AccountCreate, db: AsyncSession) -> Account:
    account = Account(
        user_id=user.id,
        currency=data.currency,
        balance=0,
    )
    db.add(account)
    await db.flush()
    return account


async def get_user_accounts(user: User, db: AsyncSession) -> list[Account]:
    result = await db.execute(
        select(Account)
        .where(Account.user_id == user.id)
        .where(Account.is_active == True) 
    )
    return list(result.scalars().all())


async def get_balance(account_id: uuid.UUID, user: User, db: AsyncSession) -> BalanceResponse:
    cached = await get_cached_balance(account_id, user.id)
    if cached is not None:
        return BalanceResponse(
            account_id=account_id,
            balance=Decimal(cached["balance"]),
            currency=cached["currency"],
        )

    account = await db.scalar(
        select(Account)
        .where(
            Account.id == account_id,
            Account.user_id == user.id,
        )
    )
    if not account:
        raise HTTPException(status_code=404, detail="Счет не найден")

    await set_cached_balance(account_id, user.id, account.balance, account.currency)
    return BalanceResponse(
        account_id=account.id,
        balance=account.balance,
        currency=account.currency,
    )

