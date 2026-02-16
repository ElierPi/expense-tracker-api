from test_finance import category, transaction


def test_description_search_respects_tenants_and_literal_wildcards(client, auth):
    owner, other = auth(), auth("other@example.com")
    cat, other_cat = category(client, owner), category(client, other)
    for description in ["Python course", "100% groceries", "under_score"]:
        assert transaction(client, owner, cat, description=description).status_code == 201
    transaction(client, other, other_cat, description="Python private")
    for search, expected in [
        ("PYTHON", "Python course"),
        ("%", "100% groceries"),
        ("_", "under_score"),
    ]:
        response = client.get("/api/v1/transactions", params={"search": search}, headers=owner)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["description"] == expected
    assert (
        client.get("/api/v1/transactions", params={"search": " "}, headers=owner).status_code == 422
    )
