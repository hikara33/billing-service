import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.models import TransactionStatus, TransactionType


class TransferRequest(BaseModel):
  from_account_id: uuid.UUID
  to_account_id: uuid.UUID
  amount: Decimal = Field(gt=0)
  description: str | None = Field(default=None, max_length=500)

  @field_validator("to_account_id")
  @classmethod
  def accounts_must_differ(cls, value: uuid.UUID, info) -> uuid.UUID:
    if value == info.data.get("from_account_id"):
      raise ValueError("Нельзя переводить на тот же счёт")

    return value


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