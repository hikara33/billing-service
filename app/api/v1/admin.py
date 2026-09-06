from fastapi import APIRouter, status, Depends
from typing import Annotated

from app.models.models import UserRole, User
from app.core.dependencies import require_roles
from app.workers.tasks import process_billing
from app.workers.celery_app import celery_app

AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPPORT))]
router = APIRouter()


@router.post("/trigger-billing", status_code=status.HTTP_202_ACCEPTED)
async def trigger_billing(admin: AdminUser):
  task = process_billing.delay()
  return { "task_id": task.id, "status": "queued" }


@router.post("/task/{task_id}")
async def get_task_status(task_id: str, admin: AdminUser):
  task = celery_app.AsyncResult(task_id)
  return {
    "task_id": task_id,
    "status": task.status,
    "result": task.result if task.ready() else None
  }
