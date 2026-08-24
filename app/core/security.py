import hashlib
import secrets
from datetime import datetime, timezone, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(psw: str) -> str:
  return pwd_context.hash(psw)

def verify_password(plain: str, hash: str) -> bool:
  return pwd_context.verify(plain, hash)


def create_access_token(user_id: str) -> str:
  expire = datetime.now(timezone.utc) + timedelta(
    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
  )
  paylod = { "sub": user_id, "exp": expire, "type": "access" }
  return jwt.encode(paylod, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> str:
  try:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.ALGORITHM)
    if payload.get("type") != "access":
      raise JWTError("Wrong token type")
    user_id = payload["sub"]
    return user_id
  except JWTError:
    raise

def generate_refresh_token() -> str:
  return secrets.token_urlsafe(64)

def hash_token(token: str) -> str:
  return hashlib.sha256(token.encode()).hexdigest()
