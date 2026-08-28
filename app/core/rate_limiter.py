from fastapi import HTTPException, Request, status
from app.core.redis import redis_client


async def check_rate_limit(
    key: str,
    limit: int,
    window: int,
    error_detail: str = "Слишком много запросов",    
) -> None:
  redis_key = f"rate_limit:{key}"

  count = await redis_client.incr(redis_key)

  if count == 1:
    await redis_client.expire(redis_key, window)

  if count > limit:
    ttl = await redis_client.ttl(redis_key)
    raise HTTPException(
      status_code = status.HTTP_429_TOO_MANY_REQUESTS,
      detail=error_detail,
      headers={"Retry-After": str(ttl)},
    )


async def check_login_rate_limit(email: str, ip: str) -> None:
  await check_rate_limit(
    key=f"login:ip:{ip}",
    limit=20,
    window=60,
    error_detail="Слишком много попыток входа"
  )
  await check_rate_limit(
    key=f"login:email:{email}",
    limit=5,
    window=900,
    error_detail="Слишком много попыток входа. Попробуйте через 15 минут"
  )


async def check_register_rate_limit(ip: str) -> None:
  await check_rate_limit(
    key=f"register:ip:{ip}",
    limit=5,
    window=3600,
    error_detail="Слишком много регистраций"
  )


async def check_transfer_rate_limit(user_id: str) -> None:
  await check_rate_limit(
    key=f"transfer:user:{user_id}",
    limit=30,
    window=60,
    error_detail="Слишком много переводов. Подождите немного"
  )
