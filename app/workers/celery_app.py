from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "billing",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
)


celery_app.conf.beat_schedule = {
  "process-billing-daily": {
    "task": "app.workers.tasks.process_billing",
    "schedule": crontab(hour=0, minute=0)
  },
  "cleanup-expired-tokens-daily": {
    "task": "app.workers.tasks.cleanup_expired_token",
    "shedule": crontab(hour=3, minute=0)
  }
}