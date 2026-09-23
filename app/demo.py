"""Create an explicit, atomic demo dataset: python -m app.demo."""

from datetime import date
from decimal import Decimal
from getpass import getpass

from sqlalchemy import select

from app.auth import Register
from app.core.database import SessionLocal
from app.core.security import password_hasher
from app.models import Category, Transaction, User


def main():
    body = Register(email=input("Demo email: ").strip(), password=getpass("Password (12+ chars): "))
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.email == str(body.email))):
            raise SystemExit("Email already exists. Use a new email; nothing was modified.")
        user = User(
            email=str(body.email),
            password_hash=password_hasher.hash(body.password.get_secret_value()),
        )
        db.add(user)
        db.flush()
        food, salary = (
            Category(owner_id=user.id, name="Food"),
            Category(owner_id=user.id, name="Salary"),
        )
        db.add_all([food, salary])
        db.flush()
        db.add_all(
            [
                Transaction(
                    owner_id=user.id,
                    category_id=salary.id,
                    amount=Decimal("5000000.00"),
                    currency="COP",
                    kind="income",
                    description="Monthly salary",
                    occurred_on=date.today(),
                ),
                Transaction(
                    owner_id=user.id,
                    category_id=food.id,
                    amount=Decimal("35000.50"),
                    currency="COP",
                    kind="expense",
                    description="Lunch",
                    occurred_on=date.today(),
                ),
            ]
        )
    print("Demo created. Sign in with the email and password you entered.")


if __name__ == "__main__":
    main()
