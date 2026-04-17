from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, extract, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models import Transaction, User
from app.schemas import Currency

router = APIRouter(tags=["Reports"])


class MonthSummary(BaseModel):
    month: int
    income: Decimal
    expense: Decimal
    balance: Decimal


class YearSummary(BaseModel):
    year: int
    currency: Currency
    income: Decimal
    expense: Decimal
    balance: Decimal
    months: list[MonthSummary]


@router.get("/reports/yearly", response_model=YearSummary)
def yearly_report(
    year: int = Query(ge=1900, le=9998),
    currency: Currency = Currency.COP,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from datetime import date

    month = extract("month", Transaction.occurred_on)
    rows = db.execute(
        select(
            month.label("month"),
            func.sum(case((Transaction.kind == "income", Transaction.amount), else_=0)).label(
                "income"
            ),
            func.sum(case((Transaction.kind == "expense", Transaction.amount), else_=0)).label(
                "expense"
            ),
        )
        .where(
            Transaction.owner_id == user.id,
            Transaction.currency == currency,
            Transaction.occurred_on >= date(year, 1, 1),
            Transaction.occurred_on < date(year + 1, 1, 1),
        )
        .group_by(month)
    ).all()
    totals = {int(row.month): row for row in rows}
    zero = Decimal("0.00")
    months = []
    for number in range(1, 13):
        row = totals.get(number)
        income, expense = (row.income, row.expense) if row else (zero, zero)
        months.append(
            MonthSummary(month=number, income=income, expense=expense, balance=income - expense)
        )
    income = sum((item.income for item in months), zero)
    expense = sum((item.expense for item in months), zero)
    return YearSummary(
        year=year,
        currency=currency,
        income=income,
        expense=expense,
        balance=income - expense,
        months=months,
    )
