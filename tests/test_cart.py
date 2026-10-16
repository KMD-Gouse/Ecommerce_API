import pytest
from sqlalchemy import select

from app.models import Cart


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