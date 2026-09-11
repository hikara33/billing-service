import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.core.database import TaskSessionFactory
from app.models.models import RefreshToken
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
  return asyncio.run(coro)


@celery_app.task(
  name="app.workers.tasks.process_billing",
  bind=True,
  max_retries=3,
  default_retry_delay=60
)
def process_billing(self):
  logger.info("starting process billing")

  async def _run():
    async with TaskSessionFactory() as db:
      try:
        from app.services.billing_service import process_due_subscriptions
        result = await process_due_subscriptions(db)
        logger.info(f"billing done: {result}")
        return result
      except Exception as exc:
        await db.rollback()
        logger.info(f"billing failed: {exc}")
        raise

  try:
    return run_async(_run())
  except Exception as exc:
    raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
  logger.info("cleaning up expired refresh tokens")

  async def _run():
    async with TaskSessionFactory() as db:
      try:
        now = datetime.now(timezone.utc)
        await db.execute(
          delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await db.commit()
        logger.info("expired tokens cleaned up")
      except Exception as exc:
        await db.rollback()
        logger.info(f"cleanup failed: {exc}")
        raise

  run_async(_run())