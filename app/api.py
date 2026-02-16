from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models import Category, Transaction, User
from app.schemas import (
    CategoryIn,
    CategoryOut,
    CategoryTotal,
    Currency,
    Kind,
    MonthlyReport,
    TransactionIn,
    TransactionOut,
    TransactionPage,
)

router = APIRouter()


def owned_category(db: Session, user_id: UUID, category_id: UUID) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.owner_id == user_id)
    )
    if category is None:
        raise HTTPException(404, "Category not found")
    return category


def owned_transaction(db: Session, user_id: UUID, transaction_id: UUID) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.owner_id == user_id,
        )
    )
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    return transaction


def commit_transaction(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23503":
            raise HTTPException(
                409, "Category was changed or removed; retry the operation"
            ) from None
        raise


@router.post("/categories", response_model=CategoryOut, status_code=201, tags=["Categories"])
def create_category(
    body: CategoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    category = Category(owner_id=user.id, name=body.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Category already exists") from None
        raise
    return category


@router.get("/categories", response_model=list[CategoryOut], tags=["Categories"])
def list_categories(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Category)
        .where(Category.owner_id == user.id)
        .order_by(Category.name, Category.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.delete("/categories/{category_id}", status_code=204, tags=["Categories"])
def delete_category(
    category_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    db.delete(owned_category(db, user.id, category_id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) in {"23503", "23001"}:
            raise HTTPException(409, "Category contains transactions") from None
        raise
    return Response(status_code=204)


@router.post("/transactions", response_model=TransactionOut, status_code=201, tags=["Transactions"])
def create_transaction(
    body: TransactionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    owned_category(db, user.id, body.category_id)
    transaction = Transaction(owner_id=user.id, **body.model_dump())
    db.add(transaction)
    commit_transaction(db)
    return transaction


@router.get("/transactions", response_model=TransactionPage, tags=["Transactions"])
def list_transactions(
    start: date | None = None,
    end: date | None = None,
    kind: Kind | None = None,
    currency: Currency | None = None,
    category_id: UUID | None = None,
    search: str | None = Query(None, min_length=1, max_length=280),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if start and end and start > end:
        raise HTTPException(422, "start must be on or before end")
    filters = [Transaction.owner_id == user.id]
    if start:
        filters.append(Transaction.occurred_on >= start)
    if end:
        filters.append(Transaction.occurred_on <= end)
    if kind:
        filters.append(Transaction.kind == kind)
    if currency:
        filters.append(Transaction.currency == currency)
    if category_id:
        filters.append(Transaction.category_id == category_id)
    if search is not None:
        if not search.strip():
            raise HTTPException(422, "Search must contain non-whitespace characters")
        filters.append(Transaction.description.icontains(search.strip(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters))
    items = db.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.occurred_on.desc(), Transaction.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/transactions/{transaction_id}", response_model=TransactionOut, tags=["Transactions"])
def get_transaction(
    transaction_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return owned_transaction(db, user.id, transaction_id)


@router.put("/transactions/{transaction_id}", response_model=TransactionOut, tags=["Transactions"])
def replace_transaction(
    transaction_id: UUID,
    body: TransactionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    transaction = owned_transaction(db, user.id, transaction_id)
    owned_category(db, user.id, body.category_id)
    for key, value in body.model_dump().items():
        setattr(transaction, key, value)
    commit_transaction(db)
    return transaction


@router.delete("/transactions/{transaction_id}", status_code=204, tags=["Transactions"])
def delete_transaction(
    transaction_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.delete(owned_transaction(db, user.id, transaction_id))
    db.commit()
    return Response(status_code=204)


@router.get("/reports/monthly", response_model=MonthlyReport, tags=["Reports"])
def monthly_report(
    year: int = Query(ge=1900, le=9998),
    month: int = Query(ge=1, le=12),
    currency: Currency = Currency.COP,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.sum(case((Transaction.kind == "income", Transaction.amount), else_=0)).label(
                "income"
            ),
            func.sum(case((Transaction.kind == "expense", Transaction.amount), else_=0)).label(
                "expense"
            ),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            Transaction.owner_id == user.id,
            Transaction.currency == currency,
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
        .group_by(Category.id, Category.name)
        .order_by(Category.name, Category.id),
    ).all()
    categories = [
        CategoryTotal(category_id=r.id, name=r.name, income=r.income, expense=r.expense)
        for r in rows
    ]
    income = sum((r.income for r in categories), Decimal("0.00"))
    expense = sum((r.expense for r in categories), Decimal("0.00"))
    return MonthlyReport(
        year=year,
        month=month,
        currency=currency,
        income=income,
        expense=expense,
        balance=income - expense,
        categories=categories,
    )
