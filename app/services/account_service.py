import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, User
from app.models.models import Transaction, TransactionStatus, TransactionType
from app.schemas.accounts import AccountCreate, DepositRequest


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


async def deposit(
    account_id: uuid.UUID,
    data: DepositRequest,
    user: User,
    db: AsyncSession,
) -> Transaction:
    result = await db.execute(
        select(Account)
        .where(Account.id == account_id)
        .where(Account.is_active == True) 
        .with_for_update()
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт не найден")

    if account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к счёту")

    account.balance += data.amount

    tx = Transaction(
        to_account_id=account.id,
        amount=data.amount,
        currency=account.currency,
        type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description="Пополнение счёта",
    )
    db.add(tx)
    await db.flush()
    return tx