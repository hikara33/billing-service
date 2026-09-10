from pydantic import BaseModel


class YookassaAmount(BaseModel):
    value: str
    currency: str


class YookassaPaymentObject(BaseModel):
    id: str
    status: str
    amount: YookassaAmount
    metadata: dict


class YookassaWebhookPayload(BaseModel):
    event: str
    object: YookassaPaymentObject
