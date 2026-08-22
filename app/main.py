from fastapi import FastAPI

app = FastAPI()

@app.get("/health", tags=["system"])
async def check_health():
  return { "status": "ok" }

