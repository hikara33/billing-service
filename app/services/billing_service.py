import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Account, User
from app.models.models import (
    Invoice,
    InvoiceStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.schemas.billing import SubscribeRequest


def _next_billing_date(interval: str, from_date: datetime) -> datetime:
    if interval == "monthly":
        month = from_date.month + 1
        year = from_date.year + month // 13
        month = month if month <= 12 else 1
        return from_date.replace(year=year, month=month)
    return from_date.replace(year=from_date.year + 1)


async def _get_plan(plan_id: uuid.UUID, db: AsyncSession) -> Plan:
    plan = await db.scalar(
        select(Plan).where(Plan.id == plan_id, Plan.is_active == True) 
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тариф не найден")
    return plan


async def _get_account(account_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Account:
    account = await db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True,  
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт не найден")
    return account


async def _has_active_subscription(user_id: uuid.UUID, plan_id: uuid.UUID, db: AsyncSession) -> bool:
    existing = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.plan_id == plan_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    return existing is not None


async def get_plans(db: AsyncSession) -> list[Plan]:
    plans = await db.scalars(
        select(Plan).where(Plan.is_active == True)  
    )
    return list(plans.all())


async def subscribe(data: SubscribeRequest, user: User, db: AsyncSession) -> Subscription:
    plan = await _get_plan(data.plan_id, db)
    account = await _get_account(data.account_id, user.id, db)

    if await _has_active_subscription(user.id, plan.id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У вас уже есть активная подписка на этот тариф",
        )

    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        account_id=account.id,
        status=SubscriptionStatus.ACTIVE,
        started_at=now,
        next_billing_date=_next_billing_date(plan.interval.value, now),
    )
    db.add(subscription)
    await db.flush()

    await _charge_subscription(subscription, plan, account, db)
    
    return await db.scalar(
        select(Subscription)
        .where(Subscription.id == subscription.id)
        .options(selectinload(Subscription.plan))
    )


async def cancel_subscription(
    subscription_id: uuid.UUID, user: User, db: AsyncSession
) -> Subscription:
    subscription = await db.scalar(
        select(Subscription)
        .where(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
        )
        .options(selectinload(Subscription.plan))
    )
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подписка не найдена")

    if subscription.status == SubscriptionStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Подписка уже отменена")

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    return subscription


async def get_user_subscriptions(user: User, db: AsyncSession) -> list[Subscription]:
    subscriptions = await db.scalars(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .options(selectinload(Subscription.plan))
        .order_by(Subscription.created_at.desc())
    )
    return list(subscriptions.all())


async def get_invoices(
    subscription_id: uuid.UUID, user: User, db: AsyncSession
) -> list[Invoice]:
    subscription = await db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
        )
    )
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подписка не найдена")

    invoices = await db.scalars(
        select(Invoice)
        .where(Invoice.subscription_id == subscription_id)
        .order_by(Invoice.created_at.desc())
    )
    return list(invoices.all())


async def _charge_subscription(
    subscription: Subscription,
    plan: Plan,
    account: Account,
    db: AsyncSession,
) -> Invoice:
    now = datetime.now(timezone.utc)
    plan_price = Decimal(str(plan.price))

    invoice = Invoice(
        subscription_id=subscription.id,
        amount=plan.price,
        currency=plan.currency,
        status=InvoiceStatus.PENDING,
        due_date=now,
    )
    db.add(invoice)
    await db.flush()

    if account.balance < plan_price:
        invoice.status = InvoiceStatus.FAILED
        subscription.status = SubscriptionStatus.SUSPENDED
        await db.flush()
        return invoice

    locked_account = await db.scalar(
        select(Account).where(Account.id == account.id).with_for_update()
    )

    if locked_account.balance < plan_price:
        invoice.status = InvoiceStatus.FAILED
        subscription.status = SubscriptionStatus.SUSPENDED
        await db.flush()
        return invoice

    locked_account.balance -= plan_price

    tx = Transaction(
        from_account_id=account.id,
        amount=plan.price,
        currency=plan.currency,
        type=TransactionType.WITHDRAWAL,
        status=TransactionStatus.COMPLETED,
        description=f"Оплата подписки: {plan.name}",
    )
    db.add(tx)
    await db.flush()

    invoice.status = InvoiceStatus.PAID
    invoice.transaction_id = tx.id
    invoice.paid_at = now
    await db.flush()
    return invoice


async def process_due_subscriptions(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)

    due_subscriptions = await db.scalars(
        select(Subscription)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.next_billing_date <= now,
        )
    )

    charged = 0
    failed = 0

    for subscription in due_subscriptions.all():
        plan = await db.scalar(select(Plan).where(Plan.id == subscription.plan_id))
        account = await db.scalar(select(Account).where(Account.id == subscription.account_id))

        invoice = await _charge_subscription(subscription, plan, account, db)

        if invoice.status == InvoiceStatus.PAID:
            subscription.next_billing_date = _next_billing_date(plan.interval.value, now)
            charged += 1
        else:
            failed += 1

    await db.commit()
    return {"charged": charged, "failed": failed}