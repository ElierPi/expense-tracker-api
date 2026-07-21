import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app import demo
from app.core.database import SessionLocal
from app.models import Category, Transaction, User


def test_demo_creates_usable_data_and_duplicate_run_preserves_existing_records(client, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "demo@example.com")
    monkeypatch.setattr(demo, "getpass", lambda _: "Demo-password-12345")
    demo.main()
    with pytest.raises(SystemExit, match="Email already exists"):
        demo.main()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Category)) == 2
        assert db.scalar(select(func.count()).select_from(Transaction)) == 2
    assert (
        client.post(
            "/api/v1/auth/token",
            data={
                "username": "demo@example.com",
                "password": "Demo-password-12345",
            },
        ).status_code
        == 200
    )


def test_demo_validates_credentials_before_writing(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "invalid")
    monkeypatch.setattr(demo, "getpass", lambda _: "short")
    with pytest.raises(ValidationError):
        demo.main()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
