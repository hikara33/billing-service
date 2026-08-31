from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.payments import router as payments_router
from app.api.v1.billing import router as billing_router

from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
  print(f"Starting billing service [{settings.APP_ENV}]")
  yield
  print("Shutting down billing service")

app = FastAPI(
  title="Billing Service",
  description="Сервис переводов и управления счетами",
  version="1.0.0",
  lifespan=lifespan,
  docs_url="/docs",
  redoc_url="/redoc",
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(accounts_router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])

@app.get("/health", tags=["system"])
async def check_health():
  return { "status": "ok", "env": settings.APP_ENV }

