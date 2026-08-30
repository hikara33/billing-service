import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.models.models import PlanInterval, InvoiceStatus, SubscriptionStatus


class PlanResponse(BaseModel):
  id: uuid.UUID
  name: str
  description: Optional[str]
  price: Decimal
  currency: str
  interval: PlanInterval
  is_active: bool

  model_config = { "from_attributes": True }


class SubscribeRequest(BaseModel):
  plan_id: uuid.UUID
  account_id: uuid.UUID


class SubscriptionResponse(BaseModel):
  id: uuid.UUID
  plan: PlanResponse
  status: SubscriptionStatus
  started_at: datetime
  next_billing_date: datetime
  cancelled_at: Optional[datetime]

  model_config = { "from_attributes": True }


class InvoiceResponse(BaseModel):
  id: uuid.UUID
  amount: Decimal
  currency: str
  status: InvoiceStatus
  due_date: datetime
  paid_at: Optional[datetime]
  created_at: datetime

  model_config = { "from_attributes": True }
