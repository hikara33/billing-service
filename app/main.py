from contextlib import asynccontextmanager

from fastapi import FastAPI

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

@app.get("/health", tags=["system"])
async def check_health():
  return { "status": "ok", "env": settings.APP_ENV }

