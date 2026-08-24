import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status, Response
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
)
from app.core.config import settings
from app.models import User
from app.models.models import RefreshToken
from app.schemas.auth import UserRegister, TokenPair, AccessTokenResponse


async def register_user(data: UserRegister, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email уже зарегистрирован",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush() 
    return user


async def login_user(email: str, password: str, db: AsyncSession, response: Response) -> AccessTokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    tokens = await _issue_token_pair(user, db)

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,      
        secure=settings.APP_ENV == "production",         
        samesite="strict",   
        max_age=60 * 60 * 24 * 7, 
    )

    return { "access_token": tokens.access_token, "token_type": tokens.token_type}


async def refresh_tokens(raw_refresh_token: str, db: AsyncSession, response: Response) -> AccessTokenResponse:
    token_hash = hash_token(raw_refresh_token)

    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.is_revoked == False) 
    )
    stored = result.scalar_one_or_none()

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token не найден или уже использован",
        )

    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token истёк",
        )

    stored.is_revoked = True
    await db.flush()

    result = await db.execute(select(User).where(User.id == stored.user_id))
    user = result.scalar_one()

    tokens = await _issue_token_pair(user, db)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="strict",
        max_age=60 * 60 * 24 * 7,
    )
    return {"access_token": tokens.access_token, "token_type": tokens.token_type}


async def logout_user(raw_refresh_token: str, db: AsyncSession, response: Response) -> None:
    token_hash = hash_token(raw_refresh_token)
    response.delete_cookie("refresh_token")
    await db.execute(
        delete(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )


async def logout_all(user_id: uuid.UUID, db: AsyncSession) -> None:
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == user_id)
    )


async def _issue_token_pair(user: User, db: AsyncSession) -> TokenPair:
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.expires_at < datetime.now(timezone.utc),
        )
    )

    raw_refresh = generate_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_token)

    access_token = create_access_token(str(user.id))

    return TokenPair(access_token=access_token, refresh_token=raw_refresh)