from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import owned_category
from app.core.database import get_db
from app.core.security import current_user
from app.models import User
from app.schemas import CategoryIn, CategoryOut

router = APIRouter(tags=["Categories"])


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: UUID,
    body: CategoryIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    category = owned_category(db, user.id, category_id)
    category.name = body.name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Category already exists") from None
        raise
    return category
