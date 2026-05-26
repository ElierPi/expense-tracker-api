import csv
from io import StringIO

from test_finance import category, transaction

from app.features import csv_export


def test_export_is_private_exact_and_escapes_spreadsheet_formulas(client, auth):
    owner, other = auth(), auth("other@example.com")
    cat = category(client, owner, "=HYPERLINK(unsafe)")
    for description in ["=1+1", "  @SUM(1)", "\tformula", 'Normal, "quoted" text']:
        transaction(client, owner, cat, amount="0.10", description=description)
    transaction(client, other, category(client, other), description="private")
    transaction(client, owner, cat, currency="USD")
    response = client.get(
        "/api/v1/exports/transactions.csv",
        headers=owner,
        params={
            "start": "2026-10-01",
            "end": "2026-10-31",
            "currency": "COP",
        },
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(response.text)))
    assert len(rows) == 4
    assert all(row["amount"] == "0.10" and row["category"].startswith("'=") for row in rows)
    assert any(row["description"] == "'=1+1" for row in rows)
    assert any(row["description"] == "'@SUM(1)" for row in rows)
    assert any(row["description"] == 'Normal, "quoted" text' for row in rows)


def test_export_rejects_large_ranges_and_never_silently_truncates(client, auth, monkeypatch):
    headers = auth()
    cat = category(client, headers)
    transaction(client, headers, cat)
    transaction(client, headers, cat)
    monkeypatch.setattr(csv_export, "MAX_EXPORT_ROWS", 1)
    url = "/api/v1/exports/transactions.csv"
    for params in [
        {"start": "2026-10-31", "end": "2026-10-01"},
        {"start": "2025-01-01", "end": "2026-10-31"},
    ]:
        assert client.get(url, headers=headers, params=params).status_code == 422
    assert (
        client.get(
            url,
            headers=headers,
            params={
                "start": "2026-10-01",
                "end": "2026-10-31",
            },
        ).status_code
        == 413
    )
