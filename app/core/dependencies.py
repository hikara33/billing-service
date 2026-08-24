import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User

bearer_scheme = HTTPBearer()


async def get_current_user(
  credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
  db: AsyncSession = Depends(get_db),
) -> User:
  credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    etail="Невалидный токен",
    headers={"WWW-Authenticate": "Bearer"},
  ) 
  try:
    user_id = decode_access_token(credentials.credentials)
  except JWTError:
    raise credentials_exception

  result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
  user = result.scalar_one_or_none()

  if user is None or not user.is_active:
    raise credentials_exception

  return user


CurrentUser = Annotated[User, Depends(get_current_user)]