import pytest


@pytest.fixture
def categorized_product(client, admin_headers):
    category_response = client.post(
        "/categories",
        headers=admin_headers,
        json={"name": "Accessories"},
    )
    assert category_response.status_code == 201

    category = category_response.json()

    product_response = client.post(
        "/products",
        headers=admin_headers,
        json={
            "name": "Wireless Mouse",
            "price": "499.00",
            "stock": 10,
            "category_id": category["id"],
        },
    )
    assert product_response.status_code == 201

    return product_response.json(), category


def test_product_returns_category(client, categorized_product):
    product, category = categorized_product

    assert product["category_id"] == category["id"]

    response = client.get(f"/products/{product['id']}")

    assert response.status_code == 200
    assert response.json()["category_id"] == category["id"]

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == [product]


def test_category_can_be_changed_and_removed(
    client,
    admin_headers,
    categorized_product,
):
    product, _ = categorized_product
    path = f"/products/{product['id']}"

    response = client.post(
        "/categories",
        headers=admin_headers,
        json={"name": "Electronics"},
    )
    assert response.status_code == 201

    new_category = response.json()

    response = client.patch(
        path,
        headers=admin_headers,
        json={"category_id": new_category["id"]},
    )
    assert response.status_code == 200
    assert response.json()["category_id"] == new_category["id"]

    # Omitting category_id must preserve the current category.
    response = client.patch(
        path,
        headers=admin_headers,
        json={"stock": 15},
    )
    assert response.status_code == 200
    assert response.json()["category_id"] == new_category["id"]

    # Explicit null must remove the category.
    response = client.patch(
        path,
        headers=admin_headers,
        json={"category_id": None},
    )
    assert response.status_code == 200

    saved = client.get(path).json()

    assert saved["category_id"] is None
    assert saved["stock"] == 15


def test_missing_category_does_not_create_product(
    client,
    admin_headers,
):
    response = client.post(
        "/products",
        headers=admin_headers,
        json={
            "name": "Wireless Mouse",
            "price": "499.00",
            "stock": 10,
            "category_id": 999999,
        },
    )

    assert response.status_code == 404
    assert client.get("/products").json() == []


def test_missing_category_leaves_product_unchanged(
    client,
    admin_headers,
    categorized_product,
):
    product, _ = categorized_product
    path = f"/products/{product['id']}"

    response = client.patch(
        path,
        headers=admin_headers,
        json={
            "stock": 99,
            "category_id": 999999,
        },
    )

    assert response.status_code == 404
    assert client.get(path).json() == product


@pytest.mark.parametrize("field", ["name", "price", "stock"])
def test_required_product_fields_cannot_be_cleared(
    client,
    admin_headers,
    categorized_product,
    field,
):
    product, _ = categorized_product
    path = f"/products/{product['id']}"

    response = client.patch(
        path,
        headers=admin_headers,
        json={field: None},
    )

    assert response.status_code == 422
    assert client.get(path).json() == product