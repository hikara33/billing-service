import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.models import TransactionStatus, TransactionType


class TransferRequest(BaseModel):
  from_account_id: uuid.UUID
  to_account_number: str
  amount: Decimal = Field(gt=0)
  description: str | None = Field(default=None, max_length=500)


class TransactionResponse(BaseModel):
  id: uuid.UUID
  from_account_id: uuid.UUID | None
  to_account_id: uuid.UUID | None
  amount: Decimal
  currency: str
  type: TransactionType
  status: TransactionStatus
  description: str | None
  created_at: datetime

  model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
  items: list[TransactionResponse]
  total: int
  page: int
  size: int


class DepositRequest(BaseModel):
  amount: Decimal = Field(gt=0, le=1_000_000)
  currency: str
  account_id: uuid.UUID
