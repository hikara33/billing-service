import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_balance
from app.models import Account
from app.models.models import (
    Transaction,
    TransactionStatus,
    TransactionType,
    Payment,
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
    Invoice,
    InvoiceStatus
)
from app.integrations.yookassa.schemas import YookassaWebhookPayload


async def handle_yookassa_webhook(
        payload: YookassaWebhookPayload,
        db: AsyncSession
):
    if payload.event != "payment.succeeded":
        return

    payment: Payment | None = await db.scalar(
        select(Payment).where(
            Payment.provider_payment_id == payload.object.id,
            Payment.status == PaymentStatus.PENDING
        )
    )
    if not payment:
        return

    payment_type = payload.object.metadata.get("type")

    if payment_type == "subscription":
        await _handle_subscribe_yookassa_webhook(payment, payload.object.metadata, db)
    else:
        await _handle_deposit_yookassa_webhook(payment, db)

    payment.status = PaymentStatus.SUCCEEDED
    await db.flush()


async def _handle_deposit_yookassa_webhook(
        payment: Payment,
        db: AsyncSession
):
    account: Account | None = await db.scalar(
        select(Account)
        .where(Account.id == payment.account_id)
        .with_for_update()
    )
    if not account:
        return

    account.balance += payment.amount

    tx = Transaction(
        to_account_id=account.id,
        amount=payment.amount,
        currency=payment.currency,
        type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=f"Пополнение через ЮKassa: {payment.provider_payment_id}",
    )
    db.add(tx)
    await db.flush()
    await invalidate_balance(account.id, account.user_id)


async def _handle_subscribe_yookassa_webhook(
        payment: Payment,
        metadata: dict,
        db: AsyncSession
):
    subscription_id = metadata.get("subscription_id")
    if not subscription_id:
        return

    subscription: Subscription | None = await db.scalar(
        select(Subscription)
        .where(Subscription.id == uuid.UUID(subscription_id))
        .with_for_update()
    )
    if not subscription:
        return

    subscription.status = SubscriptionStatus.ACTIVE

    now = datetime.now(timezone.utc)

    invoice = Invoice(
        subscription_id=subscription.id,
        amount=payment.amount,
        currency=payment.currency,
        status=InvoiceStatus.PAID,
        due_date=now,
        paid_at=now,
    )
    db.add(invoice)
    await db.flush()
