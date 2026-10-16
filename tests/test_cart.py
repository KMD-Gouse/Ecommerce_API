import pytest
from sqlalchemy import select

from app.models import Cart, Order


@pytest.fixture
def cart_product(client, admin_headers):
    response = client.post(
        "/products",
        headers=admin_headers,
        json={
            "name": "Practice Mouse",
            "price": "500.00",
            "stock": 5,
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def test_empty_cart_does_not_create_a_database_row(
    client,
    customer_headers,
    session_factory,
):
    response = client.get(
        "/cart",
        headers=customer_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": None,
        "items": [],
        "total_amount": "0.00",
    }

    with session_factory() as db:
        assert db.scalars(select(Cart)).all() == []


def test_add_set_and_remove_item(
    client,
    customer_headers,
    cart_product,
):
    product_id = cart_product["id"]

    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": product_id,
            "quantity": 2,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["items"][0]["quantity"] == 2
    assert response.json()["total_amount"] == "1000.00"

    # POST adds to the current quantity: 2 + 1 = 3.
    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": product_id,
            "quantity": 1,
        },
    )

    assert response.status_code == 201, response.text
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["quantity"] == 3

    # PATCH sets the quantity to 1.
    response = client.patch(
        f"/cart/items/{product_id}",
        headers=customer_headers,
        json={"quantity": 1},
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["quantity"] == 1
    assert response.json()["total_amount"] == "500.00"

    response = client.delete(
        f"/cart/items/{product_id}",
        headers=customer_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["total_amount"] == "0.00"

    # Putting something in a cart never deducts stock.
    saved_product = client.get(
        f"/products/{product_id}"
    ).json()

    assert saved_product["stock"] == 5


def test_cart_shows_current_price(
    client,
    customer_headers,
    admin_headers,
    cart_product,
):
    product_id = cart_product["id"]

    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": product_id,
            "quantity": 2,
        },
    )

    assert response.status_code == 201

    response = client.patch(
        f"/products/{product_id}",
        headers=admin_headers,
        json={"price": "600.00"},
    )

    assert response.status_code == 200

    response = client.get(
        "/cart",
        headers=customer_headers,
    )

    assert response.json()["items"][0]["unit_price"] == "600.00"
    assert response.json()["total_amount"] == "1200.00"


def test_invalid_or_unavailable_product_is_not_added(
    client,
    customer_headers,
    cart_product,
):
    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": 999999,
            "quantity": 1,
        },
    )

    assert response.status_code == 404
    assert client.get(
        "/cart",
        headers=customer_headers,
    ).json()["items"] == []

    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": cart_product["id"],
            "quantity": 6,
        },
    )

    assert response.status_code == 409
    assert client.get(
        "/cart",
        headers=customer_headers,
    ).json()["items"] == []


def test_product_in_cart_cannot_be_deleted(
    client,
    customer_headers,
    admin_headers,
    cart_product,
):
    product_id = cart_product["id"]

    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={
            "product_id": product_id,
            "quantity": 1,
        },
    )

    assert response.status_code == 201

    response = client.delete(
        f"/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/cart", None),
        (
            "post",
            "/cart/items",
            {"product_id": 1, "quantity": 1},
        ),
        ("patch", "/cart/items/1", {"quantity": 2}),
        ("delete", "/cart/items/1", None),
    ],
)
def test_cart_routes_require_login(client, method, path, body):
    response = client.request(
        method,
        path,
        json=body,
    )

    assert response.status_code == 401
def test_checkout_creates_one_order_and_retry_returns_it(
    client,
    customer_headers,
    cart_product,
    session_factory,
):
    product_id = cart_product["id"]
    headers = {
        **customer_headers,
        "Idempotency-Key": "checkout-test-001",
    }

    add_response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={"product_id": product_id, "quantity": 2},
    )
    assert add_response.status_code == 201, add_response.text

    first = client.post("/cart/checkout", headers=headers)
    assert first.status_code == 201, first.text

    order = first.json()["order"]
    assert order["total_amount"] == "1000.00"
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["unit_price"] == "500.00"

    assert client.get(
        "/cart",
        headers=customer_headers,
    ).json()["items"] == []

    assert client.get(
        f"/products/{product_id}"
    ).json()["stock"] == 3

    # Simulate a client retrying because it missed the first response.
    retry = client.post("/cart/checkout", headers=headers)
    assert retry.status_code == 201, retry.text
    assert retry.json()["order"]["id"] == order["id"]

    assert client.get(
        f"/products/{product_id}"
    ).json()["stock"] == 3

    with session_factory() as db:
        assert len(db.scalars(select(Order)).all()) == 1


def test_checkout_key_cannot_be_reused_for_changed_cart(
    client,
    customer_headers,
    cart_product,
):
    product_id = cart_product["id"]
    first_headers = {
        **customer_headers,
        "Idempotency-Key": "checkout-test-002",
    }

    client.post(
        "/cart/items",
        headers=customer_headers,
        json={"product_id": product_id, "quantity": 2},
    )
    first = client.post("/cart/checkout", headers=first_headers)
    assert first.status_code == 201, first.text

    # Put a different quantity in the cart.
    add_response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={"product_id": product_id, "quantity": 1},
    )
    assert add_response.status_code == 201, add_response.text

    reused = client.post("/cart/checkout", headers=first_headers)
    assert reused.status_code == 409, reused.text
    assert client.get(
        f"/products/{product_id}"
    ).json()["stock"] == 3

    # A new purchase needs a new key.
    second = client.post(
        "/cart/checkout",
        headers={
            **customer_headers,
            "Idempotency-Key": "checkout-test-003",
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["order"]["id"] != first.json()["order"]["id"]
    assert client.get(
        f"/products/{product_id}"
    ).json()["stock"] == 2


def test_failed_checkout_keeps_cart_and_stock(
    client,
    customer_headers,
    admin_headers,
    cart_product,
    session_factory,
):
    product_id = cart_product["id"]

    add_response = client.post(
        "/cart/items",
        headers=customer_headers,
        json={"product_id": product_id, "quantity": 2},
    )
    assert add_response.status_code == 201, add_response.text

    # Stock changed after the customer added the item.
    updated = client.patch(
        f"/products/{product_id}",
        headers=admin_headers,
        json={"stock": 1},
    )
    assert updated.status_code == 200, updated.text

    checkout = client.post(
        "/cart/checkout",
        headers={
            **customer_headers,
            "Idempotency-Key": "checkout-test-004",
        },
    )
    assert checkout.status_code == 409, checkout.text

    cart = client.get(
        "/cart",
        headers=customer_headers,
    ).json()
    assert cart["items"][0]["quantity"] == 2

    assert client.get(
        f"/products/{product_id}"
    ).json()["stock"] == 1

    with session_factory() as db:
        assert db.scalars(select(Order)).all() == []