from decimal import Decimal
import uuid
import hashlib
import hmac

from yookassa import Configuration, Payment

from app.core.config import settings


class YookassaClient:
    def __init__(self, shop_id: str, secret_key: str):
        Configuration.configure(shop_id, secret_key)
        self._secret_key = secret_key

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

    def verify_webhook_signature(self, body: bytes, signature: str):
        expected = hmac.new(
            self._secret_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


yookassa_client = YookassaClient(settings.yookassa_shop_id, settings.yookassa_secret_key)