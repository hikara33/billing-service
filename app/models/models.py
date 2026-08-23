import enum
import uuid
from datetime import datetime


from sqlalchemy import (
  UUID,
  Enum,
  DateTime,
  ForeignKey,
  Index,
  Numeric,
  String,
  func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransactionStatus(str, enum.Enum):
  PENDING = "pending"
  COMPLETED = "completed"
  FAILED = "failed"

class TransactionType(str, enum.Enum):
  DEPOSIT = "deposit"
  WITHDRAWAL = "withdrawal"
  TRANSFER = "transfer"


class User(Base):
  __tablename__ = "users"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
  hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
  full_name: Mapped[str] = mapped_column(String(255), nullable=False)
  is_active: Mapped[bool] = mapped_column(default=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )

  accounts: Mapped[list["Account"]] = relationship(back_populates="owner")
  refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base):
  __tablename__ = "refresh_tokens"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
  )

  token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )
  is_revoked: Mapped[bool] = mapped_column(default=False)

  user: Mapped["User"] = relationship(back_populates="refresh_tokens")

  __table_args__ = (
    Index("ix_refresh_tokens_user_id", "user_id"),
    Index("ix_refresh_tokens_token_hash", "token_hash"),
  )


class Account(Base):
  __tablename__ = "accounts"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
  )

  balance: Mapped[float] = mapped_column(Numeric(19, 4), default=0, nullable=False)
  currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
  is_active: Mapped[bool] = mapped_column(default=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )

  owner: Mapped["User"] = relationship(back_populates="accounts")
  sent_transactions: Mapped[list["Transaction"]] = relationship(
    back_populates="from_account",
    foreign_keys="Transaction.from_account_id",
  )
  received_transactions: Mapped[list["Transaction"]] = relationship(
    back_populates="to_account",
    foreign_keys="Transaction.to_account_id",
  )
  
  __table_args__ = (
    Index("ix_accounts_user_id", "user_id"),
  )


class Transaction(Base):
  __tablename__ = "transactions"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  from_account_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
  )
  to_account_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
  )
  amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
  currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
  type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
  status: Mapped[TransactionStatus] = mapped_column(
    Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False
  )
  idempotency_key: Mapped[str | None] = mapped_column(
    String(255), unique=True, nullable=True, index=True
  )
  description: Mapped[str | None] = mapped_column(String(500), nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
  )

  from_account: Mapped["Account | None"] = relationship(
    back_populates="sent_transactions", foreign_keys=[from_account_id]
  )
  to_account: Mapped["Account | None"] = relationship(
    back_populates="received_transactions", foreign_keys=[to_account_id]
  )

  __table_args__ = (
    Index("ix_transactions_from_account", "from_account_id"),
    Index("ix_transactions_to_account", "to_account_id"),
    Index("ix_transactions_created_at", "created_at"),
  )
