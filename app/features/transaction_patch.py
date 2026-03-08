from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.api import commit_transaction, owned_category, owned_transaction
from app.core.database import get_db
from app.core.security import current_user
from app.models import User
from app.schemas import Currency, Input, Kind, TransactionOut

router = APIRouter(tags=["Transactions"])


class TransactionPatch(Input):
    category_id: UUID | None = None
    amount: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    currency: Currency | None = None
    kind: Kind | None = None
    description: str | None = Field(None, max_length=280)
    occurred_on: date | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Explicit null values are not supported")
        return self


@router.patch("/transactions/{transaction_id}", response_model=TransactionOut)
def patch_transaction(
    transaction_id: UUID,
    body: TransactionPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    transaction = owned_transaction(db, user.id, transaction_id)
    changes = body.model_dump(exclude_unset=True)
    if "category_id" in changes:
        owned_category(db, user.id, changes["category_id"])
    for key, value in changes.items():
        setattr(transaction, key, value)
    commit_transaction(db)
    return transaction
