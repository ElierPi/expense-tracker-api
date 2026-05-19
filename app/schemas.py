from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Currency(StrEnum):
    COP = "COP"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    MXN = "MXN"


class Kind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CategoryIn(Input):
    name: str = Field(min_length=1, max_length=80)


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TransactionIn(Input):
    category_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency = Currency.COP
    kind: Kind
    description: str = Field(default="", max_length=280)
    occurred_on: date


class TransactionOut(TransactionIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class CategoryTotal(BaseModel):
    category_id: UUID
    name: str
    income: Decimal
    expense: Decimal


class MonthlyReport(BaseModel):
    year: int
    month: int
    currency: Currency
    income: Decimal
    expense: Decimal
    balance: Decimal
    categories: list[CategoryTotal]
