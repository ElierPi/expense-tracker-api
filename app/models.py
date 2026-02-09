from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),
        UniqueConstraint("id", "owner_id", name="uq_category_id_owner"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "owner_id"],
            ["categories.id", "categories.owner_id"],
            name="fk_transaction_category_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        CheckConstraint("kind IN ('income', 'expense')", name="ck_transaction_kind"),
        CheckConstraint("currency IN ('COP', 'USD', 'EUR', 'GBP', 'MXN')", name="ck_currency"),
        Index("ix_transaction_owner_date", "owner_id", "occurred_on"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[UUID] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    kind: Mapped[str] = mapped_column(String(7))
    description: Mapped[str] = mapped_column(String(280), default="")
    occurred_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
