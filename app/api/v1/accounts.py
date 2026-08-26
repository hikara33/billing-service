import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.schemas.accounts import AccountCreate, AccountResponse, DepositRequest
from app.schemas.payments import TransactionResponse
from app.services import account_service

router = APIRouter()


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await account_service.create_account(current_user, data, db)


@router.get("/", response_model=list[AccountResponse])
async def get_accounts(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await account_service.get_user_accounts(current_user, db)


@router.post("/{account_id}/deposit", response_model=TransactionResponse)
async def deposit(
    account_id: uuid.UUID,
    data: DepositRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await account_service.deposit(account_id, data, current_user, db)