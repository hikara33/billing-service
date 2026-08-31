import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.schemas.billing import (
    InvoiceResponse,
    PlanResponse,
    SubscribeRequest,
    SubscriptionResponse,
)
from app.services import billing_service

router = APIRouter()


@router.get("/plans", response_model=list[PlanResponse])
async def get_plans(db: AsyncSession = Depends(get_db)):
    return await billing_service.get_plans(db)


@router.post("/subscribe", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    data: SubscribeRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.subscribe(data, current_user, db)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def get_subscriptions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_user_subscriptions(current_user, db)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.cancel_subscription(subscription_id, current_user, db)


@router.get("/subscriptions/{subscription_id}/invoices", response_model=list[InvoiceResponse])
async def get_invoices(
    subscription_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_invoices(subscription_id, current_user, db)