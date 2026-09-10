from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.yookassa.client import yookassa_client
from app.integrations.yookassa.schemas import YookassaWebhookPayload

router = APIRouter()


@router.post("")
async def yookassa_webhook(
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    signature = request.headers.get("X-Content-SHA256", "")

    if not yookassa_client.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=404, detail="Invalid webhook signature")

    payload = YookassaWebhookPayload.model_validate_json(body)
    #вызов пеймент сервиса
    return { "status": "ok" }
