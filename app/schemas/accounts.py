import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Currency(StrEnum):
  RUB = "RUB"
  USD = "USD"
  EUR = "EUR"


class AccountCreate(BaseModel):
  currency: Currency = Currency.RUB

  @field_validator("currency", mode="before")
  @classmethod
  def normalize_currency(cls, value: str) -> str:
    return value.upper()


class AccountResponse(BaseModel):
  id: uuid.UUID
  user_id: uuid.UUID
  balance: Decimal
  currency: Currency
  is_active: bool
  created_at: datetime

  model_config = {"from_attributes": True}


class DepositRequest(BaseModel):
  amount: Decimal = Field(gt=0, le=1_000_000)


class BalanceResponse(BaseModel):
  account_id: uuid.UUID
  balance: Decimal
  currency: str

  model_config = {"from_attributes": True}