from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models import Transaction


def category(client, headers, name="Food"):
    response = client.post("/api/v1/categories", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def transaction(client, headers, category_id, **overrides):
    return client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "category_id": category_id,
            "amount": "100.00",
            "currency": "COP",
            "kind": "expense",
            "description": "Lunch",
            "occurred_on": "2026-10-15",
        }
        | overrides,
    )


def test_tenant_isolation_and_category_integrity(client, auth):
    alice, bob = auth("alice@example.com"), auth("bob@example.com")
    food = category(client, alice)
    assert client.get("/api/v1/categories", headers=bob).json() == []
    assert transaction(client, bob, food).status_code == 404
    created = transaction(client, alice, food)
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert client.get("/api/v1/transactions", headers=bob).json()["total"] == 0
    for method in (client.get, client.delete):
        assert method(f"/api/v1/transactions/{item_id}", headers=bob).status_code == 404
    assert (
        client.put(
            f"/api/v1/transactions/{item_id}",
            headers=bob,
            json={
                "category_id": food,
                "amount": "5.00",
                "currency": "COP",
                "kind": "expense",
                "occurred_on": "2026-10-15",
            },
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/categories/{food}", headers=bob).status_code == 404
    assert client.delete(f"/api/v1/categories/{food}", headers=alice).status_code == 409
    assert client.delete(f"/api/v1/transactions/{item_id}", headers=alice).status_code == 204
    assert client.delete(f"/api/v1/categories/{food}", headers=alice).status_code == 204


def test_monthly_report_exact_math_and_currency_boundaries(client, auth):
    headers = auth()
    food, salary = category(client, headers), category(client, headers, "Salary")
    for cat, fields in [
        (salary, {"amount": "1000.00", "kind": "income"}),
        (food, {"amount": "0.10"}),
        (food, {"amount": "0.20"}),
        (food, {"amount": "400.00", "currency": "USD"}),
        (food, {"amount": "200.00", "occurred_on": "2026-11-01"}),
        (food, {"amount": "300.00", "occurred_on": "2026-09-30"}),
    ]:
        assert transaction(client, headers, cat, **fields).status_code == 201
    response = client.get(
        "/api/v1/reports/monthly?year=2026&month=10&currency=COP", headers=headers
    )
    assert response.status_code == 200
    report = response.json()
    assert Decimal(report["income"]) == Decimal("1000.00")
    assert Decimal(report["expense"]) == Decimal("0.30")
    assert Decimal(report["balance"]) == Decimal("999.70")
    assert len(report["categories"]) == 2
    empty = client.get("/api/v1/reports/monthly?year=2026&month=12", headers=headers).json()
    assert Decimal(empty["balance"]) == 0 and empty["categories"] == []
    other = auth("other@example.com")
    assert (
        client.get("/api/v1/reports/monthly?year=2026&month=10", headers=other).json()["categories"]
        == []
    )


@pytest.mark.parametrize("amount", ["0", "-1", "1.001", "1000000000000.00", "NaN", "Infinity"])
def test_rejects_invalid_amounts(client, auth, amount):
    headers = auth()
    assert transaction(client, headers, category(client, headers), amount=amount).status_code == 422


def test_filters_pagination_update_and_duplicates(client, auth):
    headers = auth()
    cat = category(client, headers)
    assert (
        client.post("/api/v1/categories", headers=headers, json={"name": "Food"}).status_code == 409
    )
    assert (
        client.post("/api/v1/categories", headers=headers, json={"name": "   "}).status_code == 422
    )
    first = transaction(client, headers, cat).json()
    transaction(client, headers, cat, amount="500", kind="income")
    transaction(client, headers, cat, currency="USD")
    page = client.get("/api/v1/transactions?limit=1&offset=1", headers=headers).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    filtered = client.get(
        "/api/v1/transactions",
        headers=headers,
        params={
            "currency": "COP",
            "kind": "expense",
            "category_id": cat,
            "start": "2026-10-15",
            "end": "2026-10-15",
        },
    ).json()
    assert filtered["total"] == 1
    updated = client.put(
        f"/api/v1/transactions/{first['id']}",
        headers=headers,
        json={
            "category_id": cat,
            "amount": "25.50",
            "currency": "COP",
            "kind": "expense",
            "occurred_on": "2026-10-20",
            "description": "Updated",
        },
    )
    assert updated.status_code == 200
    assert Decimal(updated.json()["amount"]) == Decimal("25.50")
    assert (
        client.get(
            "/api/v1/transactions?start=2026-11-01&end=2026-10-01", headers=headers
        ).status_code
        == 422
    )
    assert client.get("/api/v1/transactions?limit=101", headers=headers).status_code == 422
    assert (
        client.get("/api/v1/reports/monthly?year=2026&month=13", headers=headers).status_code == 422
    )


def test_database_rejects_cross_tenant_category_even_without_api(client, auth):
    alice, bob = auth("alice@example.com"), auth("bob@example.com")
    cat = category(client, alice)
    bob_id = client.get("/api/v1/auth/me", headers=bob).json()["id"]
    from datetime import date

    with SessionLocal() as db:
        db.add(
            Transaction(
                owner_id=UUID(bob_id),
                category_id=UUID(cat),
                amount=Decimal("1.00"),
                currency="COP",
                kind="expense",
                description="",
                occurred_on=date(2026, 10, 1),
            )
        )
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.sqlstate == "23503"
        db.rollback()
