import pytest


PRODUCT_DATA = {
    "name": "Wireless Keyboard",
    "price": "1299.00",
    "stock": 10,
}


@pytest.mark.parametrize(
    "operation",
    ["create", "update", "delete"],
)
@pytest.mark.parametrize(
    "identity, expected_status",
    [
        ("anonymous", 401),
        ("customer", 403),
    ],
)
def test_product_writes_require_admin(
    client,
    admin_headers,
    customer_headers,
    operation,
    identity,
    expected_status,
):
    # An admin creates a product for this test.
    response = client.post(
        "/products",
        headers=admin_headers,
        json=PRODUCT_DATA,
    )

    assert response.status_code == 201, response.text

    original_product = response.json()
    product_id = original_product["id"]

    # Customers send a token; anonymous requests do not.
    headers = (
        customer_headers
        if identity == "customer"
        else {}
    )

    if operation == "create":
        response = client.post(
            "/products",
            headers=headers,
            json=PRODUCT_DATA,
        )

    elif operation == "update":
        response = client.patch(
            f"/products/{product_id}",
            headers=headers,
            json={"stock": 99},
        )

    else:
        response = client.delete(
            f"/products/{product_id}",
            headers=headers,
        )

    assert response.status_code == expected_status, response.text

    # The rejected request must leave the product unchanged.
    saved = client.get(f"/products/{product_id}")

    assert saved.status_code == 200, saved.text
    assert saved.json() == original_product

    products = client.get("/products")

    assert products.status_code == 200
    assert len(products.json()) == 1


def test_admin_can_manage_products(client, admin_headers):
    # Create.
    response = client.post(
        "/products",
        headers=admin_headers,
        json=PRODUCT_DATA,
    )

    assert response.status_code == 201, response.text

    product_id = response.json()["id"]

    # Update.
    response = client.patch(
        f"/products/{product_id}",
        headers=admin_headers,
        json={"stock": 7},
    )

    assert response.status_code == 200, response.text

    # Read without authentication: browsing stays public.
    response = client.get(f"/products/{product_id}")

    assert response.status_code == 200, response.text
    assert response.json()["stock"] == 7

    # Delete.
    response = client.delete(
        f"/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    # Confirm deletion.
    response = client.get(f"/products/{product_id}")

    assert response.status_code == 404, response.text