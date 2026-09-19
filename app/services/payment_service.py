import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.core.cache import invalidate_balance
from app.models import Account
from app.models.models import Transaction, TransactionStatus, TransactionType, Payment, PaymentStatus, PaymentProvider, User
from app.schemas.payments import TransferRequest, TransactionListResponse, DepositRequest
from app.integrations.yookassa.client import yookassa_client

from app.core.config import settings

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
    from_account_check = await db.scalar(
        select(Account).where(
            Account.id == data.from_account_id,
            Account.user_id == user_id,
        )
    )
    if not from_account_check:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к счёту")

    existing = await get_idempotent_transaction(idempotency_key, user_id, db)
    if existing is not None:
        return existing

    to_account_check = await db.scalar(
        select(Account).where(Account.account_number == data.to_account_number)
    )
    if not to_account_check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт получателя не найден")

    if from_account_check.id == to_account_check.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя переводить на тот же счёт")

    ids = sorted([from_account_check.id, to_account_check.id])
    result = await db.execute(
        select(Account)
        .where(Account.id.in_(ids))
        .where(Account.is_active == True)  # noqa: E712
        .order_by(Account.id)
        .with_for_update()
    )
    accounts = result.scalars().all()

    if len(accounts) != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Один или оба счёта не активны")

    from_account = next(a for a in accounts if a.id == from_account_check.id)
    to_account = next(a for a in accounts if a.id == to_account_check.id)

    if from_account.currency != to_account.currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Валюты счетов должны совпадать")

    if from_account.balance < data.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно средств")

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

    await invalidate_balance(from_account.id, from_account.user_id)
    await invalidate_balance(to_account.id, to_account.user_id)

    if idempotency_key:
        await redis_client.set(
            f"idempotency:{user_id}:{idempotency_key}",
            json.dumps({"transaction_id": str(tx.id), "status": tx.status.value}),
            ex=IDEMPOTENCY_TTL,
        )

    return tx


async def deposit(
        data: DepositRequest,
        user: User,
        db: AsyncSession
) -> dict:
    account = await db.scalar(
        select(Account).where(
            Account.id == data.account_id,
            Account.user_id == user.id,
            Account.is_active == True
        )
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    yookassa_payment = yookassa_client.create_payment(
        amount=data.amount,
        currency=data.currency,
        description=f"Пополнение счёта",
        return_url=settings.yookassa_return_url,
        metadata={
            "account_id": str(account.id),
            "user_id": str(user.id),
        }
    )

    payment = Payment(
        account_id=account.id,
        provider=PaymentProvider.YOOKASSA,
        provider_payment_id=yookassa_payment.id,
        amount=data.amount,
        currency=data.currency,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.flush()

    return {
        "payment_id": str(payment.id),
        "confirmation_url": yookassa_payment.confirmation.confirmation_url,
        "amount": data.amount,
        "status": payment.status,
    }


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