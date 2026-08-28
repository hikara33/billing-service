from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.core.rate_limiter import check_transfer_rate_limit
from app.models import Account
from app.models.models import TransactionStatus, TransactionType
from app.schemas.payments import (
    TransactionListResponse,
    TransactionResponse,
    TransferRequest,
)
from app.services import payment_service
import uuid

router = APIRouter()


@router.post("/transfer", response_model=TransactionResponse)
async def transfer(
    data: TransferRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(default=None),
):
    existing = await payment_service.get_idempotent_transaction(
        x_idempotency_key, current_user.id, db
    )
    if existing is not None:
        return existing

    await check_transfer_rate_limit(str(current_user.id))
    return await payment_service.transfer(data, x_idempotency_key, current_user.id, db)


@router.get("/history/{account_id}", response_model=TransactionListResponse)
async def get_history(
    account_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[TransactionStatus] = Query(default=None, alias="status"),
    type_filter: Optional[TransactionType] = Query(default=None, alias="type"),
):
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт не найден")

    return await payment_service.get_history(account_id, db, page, size, status_filter, type_filter)