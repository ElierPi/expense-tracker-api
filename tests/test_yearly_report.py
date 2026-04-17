from decimal import Decimal

from test_finance import category, transaction


def test_yearly_report_includes_empty_months_and_keeps_currencies_separate(client, auth):
    headers, other = auth(), auth("other@example.com")
    cat = category(client, headers)
    for fields in [
        {"amount": "1000", "kind": "income", "occurred_on": "2026-01-01"},
        {"amount": "0.10", "occurred_on": "2026-12-31"},
        {"amount": "0.20", "occurred_on": "2026-12-31"},
        {"amount": "200", "currency": "USD"},
        {"amount": "500", "occurred_on": "2027-01-01"},
    ]:
        assert transaction(client, headers, cat, **fields).status_code == 201
    response = client.get("/api/v1/reports/yearly?year=2026&currency=COP", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert len(result["months"]) == 12
    assert [month["month"] for month in result["months"]] == list(range(1, 13))
    assert Decimal(result["balance"]) == Decimal("999.70")
    assert Decimal(result["months"][1]["expense"]) == 0
    assert Decimal(result["months"][11]["expense"]) == Decimal("0.30")
    empty = client.get("/api/v1/reports/yearly?year=2026", headers=other).json()
    assert Decimal(empty["income"]) == 0 and len(empty["months"]) == 12
