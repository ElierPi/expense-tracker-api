import pytest
from test_finance import category, transaction


def test_partial_update_preserves_other_fields_and_rejects_foreign_categories(client, auth):
    owner, other = auth(), auth("other@example.com")
    created = transaction(client, owner, category(client, owner)).json()
    url = f"/api/v1/transactions/{created['id']}"
    patched = client.patch(url, headers=owner, json={"description": "Corrected"})
    assert patched.status_code == 200
    expected = created | {"description": "Corrected"}
    assert patched.json() == expected
    assert client.patch(url, headers=other, json={"amount": "1.00"}).status_code == 404
    assert (
        client.patch(url, headers=owner, json={"category_id": category(client, other)}).status_code
        == 404
    )
    assert client.get(url, headers=owner).json() == expected


@pytest.mark.parametrize(
    "body", [{}, {"amount": None}, {"amount": "-1"}, {"amount": "1.001"}, {"owner_id": "injected"}]
)
def test_invalid_partial_changes_fail_without_modifying_data(client, auth, body):
    headers = auth()
    created = transaction(client, headers, category(client, headers)).json()
    url = f"/api/v1/transactions/{created['id']}"
    assert client.patch(url, headers=headers, json=body).status_code == 422
    assert client.get(url, headers=headers).json() == created
