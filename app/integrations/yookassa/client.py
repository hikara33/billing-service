from decimal import Decimal
import uuid

from yookassa import Configuration, Payment


class YookassaClient:
    def __init__(self, shop_id: str, secret_key: str):
        Configuration.configure(shop_id, secret_key)

    def create_payment(
            self,
            amount: Decimal,
            currency: str,
            description: str,
            return_url: str,
            metadata: dict[str, str]
    ):
        payment = Payment.create(
            {
                "amount": {
                    "value": str(amount),
                    "currency": currency
                },
                "capture": True,
                "confirmation": {
                    "type": "redirect",
                    "url": return_url
                },
                "description": description,
                "metadata": metadata
            },
            idempotency_key=str(uuid.uuid4())
        )

        return payment