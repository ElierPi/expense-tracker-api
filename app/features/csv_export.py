import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models import Category, Transaction, User
from app.schemas import Currency, Kind

router = APIRouter(tags=["Exports"])
MAX_EXPORT_ROWS = 10_000


def spreadsheet_text(value: str) -> str:
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/exports/transactions.csv", response_class=Response)
def export_transactions(
    start: date,
    end: date,
    currency: Currency | None = None,
    kind: Kind | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not 0 <= (end - start).days <= 365:
        raise HTTPException(422, "Choose an inclusive date range of at most 366 days")
    query = select(Transaction, Category.name).join(
        Category, Category.id == Transaction.category_id
    )
    query = query.where(
        Transaction.owner_id == user.id,
        Transaction.occurred_on >= start,
        Transaction.occurred_on <= end,
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)
    if kind is not None:
        query = query.where(Transaction.kind == kind)
    rows = db.execute(
        query.order_by(Transaction.occurred_on, Transaction.id).limit(MAX_EXPORT_ROWS + 1)
    ).all()
    if len(rows) > MAX_EXPORT_ROWS:
        raise HTTPException(413, "Too many rows; narrow the export date range")
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["id", "category", "amount", "currency", "kind", "occurred_on", "description"])
    for transaction, name in rows:
        writer.writerow(
            [
                str(transaction.id),
                spreadsheet_text(name),
                format(transaction.amount, ".2f"),
                transaction.currency,
                transaction.kind,
                transaction.occurred_on.isoformat(),
                spreadsheet_text(transaction.description),
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="transactions-{start}-{end}.csv"',
        },
    )
