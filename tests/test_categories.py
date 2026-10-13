import pytest


def test_admin_can_create_and_public_can_read(client, admin_headers):
    response = client.post(
        "/categories",
        headers=admin_headers,
        json={"name": " Electronics "},
    )

    assert response.status_code == 201, response.text

    category = response.json()

    assert category["name"] == "Electronics"
    assert category["id"] > 0

    # No authentication headers: browsing is public.
    response = client.get(
        f"/categories/{category['id']}"
    )

    assert response.status_code == 200
    assert response.json() == category

    response = client.get("/categories")

    assert response.status_code == 200
    assert response.json() == [category]


def test_category_creation_requires_admin(client, customer_headers):
    response = client.post(
        "/categories",
        json={"name": "Books"},
    )

    assert response.status_code == 401

    response = client.post(
        "/categories",
        headers=customer_headers,
        json={"name": "Books"},
    )

    assert response.status_code == 403

    # Rejected requests must not create records.
    assert client.get("/categories").json() == []


def test_duplicate_category_returns_409(client, admin_headers):
    for expected_status in (201, 409):
        response = client.post(
            "/categories",
            headers=admin_headers,
            json={"name": "Books"},
        )

        assert response.status_code == expected_status

    categories = client.get("/categories").json()

    assert len(categories) == 1


@pytest.mark.parametrize(
    "name",
    ["", "   ", "A", "A" * 101],
)
def test_invalid_category_name(client, admin_headers, name):
    response = client.post(
        "/categories",
        headers=admin_headers,
        json={"name": name},
    )

    assert response.status_code == 422
    assert client.get("/categories").json() == []


def test_missing_category_returns_404(client):
    response = client.get("/categories/999999")

    assert response.status_code == 404


def test_category_pagination(client, admin_headers):
    created = []

    for name in ("Books", "Electronics", "Clothing"):
        response = client.post(
            "/categories",
            headers=admin_headers,
            json={"name": name},
        )

        assert response.status_code == 201
        created.append(response.json())

    response = client.get(
        "/categories",
        params={"limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    assert response.json() == [created[1]]

    assert client.get(
        "/categories",
        params={"limit": 101},
    ).status_code == 422

    assert client.get(
        "/categories",
        params={"offset": -1},
    ).status_code == 422