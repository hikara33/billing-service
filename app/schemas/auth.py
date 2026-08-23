import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8)
  full_name: str = Field(min_length=2, max_length=100)


class UserLogin(BaseModel):
  email: EmailStr
  password: str = Field(min_length=1)


class TokenPair(BaseModel):
  access_token: str
  refresh_token: str
  token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
  refresh_token: str


class UserResponse(BaseModel):
  id: uuid.UUID
  email: EmailStr
  full_name: str
  is_active: bool

  model_config = {"from_attributes": True}
