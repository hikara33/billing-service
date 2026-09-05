import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.core.cache import invalidate_balance
from app.models import Account
from app.models.models import Transaction, TransactionStatus, TransactionType
from app.schemas.payments import TransferRequest, TransactionListResponse

IDEMPOTENCY_TTL = 60 * 60 * 24


async def get_idempotent_transaction(
    idempotency_key: str | None,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Transaction | None:
    if not idempotency_key:
        return None

    cached = await redis_client.get(f"idempotency:{user_id}:{idempotency_key}")
    if not cached:
        return None

    tx_data = json.loads(cached)
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == uuid.UUID(tx_data["transaction_id"])
        )
    )
    return result.scalar_one_or_none()


async def transfer(
    data: TransferRequest,
    idempotency_key: str | None,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Transaction:
    result = await db.execute(
        select(Account).where(
            Account.id == data.from_account_id,
            Account.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к счёту")

    existing = await get_idempotent_transaction(idempotency_key, user_id, db)
    if existing is not None:
        return existing

    ids = sorted([data.from_account_id, data.to_account_id])

    result = await db.execute(
        select(Account)
        .where(Account.id.in_(ids))
        .where(Account.is_active == True)
        .order_by(Account.id)
        .with_for_update()
    )
    accounts = result.scalars().all()

    if len(accounts) != 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Один или оба счёта не найдены",
        )

    from_account = next(a for a in accounts if a.id == data.from_account_id)
    to_account = next(a for a in accounts if a.id == data.to_account_id)

    if from_account.currency != to_account.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Валюты счетов должны совпадать",
        )

    if from_account.balance < data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно средств",
        )

    from_account.balance -= data.amount
    to_account.balance += data.amount

    tx = Transaction(
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        amount=data.amount,
        currency=from_account.currency,
        type=TransactionType.TRANSFER,
        status=TransactionStatus.COMPLETED,
        idempotency_key=idempotency_key,
        description=data.description,
    )
    db.add(tx)
    await db.flush()

    await invalidate_balance(data.from_account_id, from_account.user_id)
    await invalidate_balance(data.to_account_id, to_account.user_id)

    if idempotency_key:
        redis_key = f"idempotency:{user_id}:{idempotency_key}"
        await redis_client.setex(
            redis_key,
            IDEMPOTENCY_TTL,
            json.dumps({"transaction_id": str(tx.id), "status": tx.status.value})
        )
    return tx


async def get_history(
    account_id: uuid.UUID,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status_filter: TransactionStatus | None = None,
    type_filter: TransactionType | None = None,
) -> TransactionListResponse:

    query = select(Transaction).where(
        or_(
            Transaction.from_account_id == account_id,
            Transaction.to_account_id == account_id,
        )
    )

    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if type_filter:
        query = query.where(Transaction.type == type_filter)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    query = query.order_by(Transaction.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    items = list(result.scalars().all())

    return TransactionListResponse(items=items, total=total, page=page, size=size)