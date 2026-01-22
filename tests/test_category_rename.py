from test_finance import category, transaction


def test_rename_preserves_transactions_and_enforces_ownership(client, auth):
    owner, outsider = auth(), auth("other@example.com")
    cat = category(client, owner)
    transaction(client, owner, cat)
    url = f"/api/v1/categories/{cat}"
    assert client.patch(url, headers=outsider, json={"name": "Stolen"}).status_code == 404
    renamed = client.patch(url, headers=owner, json={"name": "Groceries"})
    assert renamed.status_code == 200
    assert renamed.json() == {"id": cat, "name": "Groceries"}
    assert (
        client.get("/api/v1/transactions", headers=owner).json()["items"][0]["category_id"] == cat
    )
    category(client, owner, "Salary")
    assert client.patch(url, headers=owner, json={"name": "Salary"}).status_code == 409
    assert client.patch(url, headers=owner, json={"name": " "}).status_code == 422
    assert client.get("/api/v1/categories", headers=owner).json()[0]["name"] == "Groceries"
