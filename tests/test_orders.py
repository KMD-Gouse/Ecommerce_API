from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product, User


def database_state(session_factory):
    """Read saved data using a fresh session."""
    with session_factory() as db:
        return {
            "products": [
                tuple(row)
                for row in db.execute(
                    select(Product.id, Product.stock)
                    .order_by(Product.id)
                )
            ],
            "orders": [
                tuple(row)
                for row in db.execute(
                    select(
                        Order.id,
                        Order.status,
                        Order.total_amount,
                        Order.cancelled_at,
                    ).order_by(Order.id)
                )
            ],
            "items": [
                tuple(row)
                for row in db.execute(
                    select(
                        OrderItem.id,
                        OrderItem.order_id,
                        OrderItem.product_id,
                        OrderItem.quantity,
                        OrderItem.unit_price,
                    ).order_by(OrderItem.id)
                )
            ],
        }


@pytest.fixture
def catalogue(client, admin_headers):
    products = []

    for data in (
        {"name": "Keyboard", "price": "1500.00", "stock": 5},
        {"name": "Mouse", "price": "500.00", "stock": 10},
    ):
        response = client.post(
            "/products",
            headers=admin_headers,
            json=data,
        )

        assert response.status_code == 201, response.text
        products.append(response.json())

    return products


@pytest.fixture
def placed_order(client, customer_headers, catalogue):
    keyboard, mouse = catalogue

    for product, quantity in (
        (keyboard, 1),
        (mouse, 2),
    ):
        response = client.post(
            "/cart/items",
            headers=customer_headers,
            json={
                "product_id": product["id"],
                "quantity": quantity,
            },
        )
        assert response.status_code == 201, response.text

    response = client.post(
        "/cart/checkout",
        headers={
            **customer_headers,
            "Idempotency-Key": "placed-order-fixture",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()["order"]
@pytest.fixture
def other_customer_headers(client):
    response = client.post(
        "/users",
        json={
            "name": "Another Customer",
            "email": "another-customer@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 201, response.text

    response = client.post(
        "/auth/login",
        data={
            "username": "another-customer@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 200, response.text

    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        )
    }
def test_order_total_items_owner_and_stock(
    client,
    customer_headers,
    catalogue,
    placed_order,
):
    keyboard, mouse = catalogue

    profile = client.get(
        "/users/me",
        headers=customer_headers,
    ).json()

    assert placed_order["user_id"] == profile["id"]
    assert placed_order["status"] == "placed"
    assert placed_order["created_at"] is not None
    assert placed_order["cancelled_at"] is None
    assert Decimal(placed_order["total_amount"]) == Decimal("2500.00")

    items = {
        item["product_id"]: item
        for item in placed_order["items"]
    }

    assert len(items) == 2
    assert items[keyboard["id"]]["quantity"] == 1
    assert items[mouse["id"]]["quantity"] == 2

    assert Decimal(
        items[keyboard["id"]]["unit_price"]
    ) == Decimal("1500.00")

    assert Decimal(
        items[mouse["id"]]["unit_price"]
    ) == Decimal("500.00")

    assert client.get(
        f"/products/{keyboard['id']}"
    ).json()["stock"] == 4

    assert client.get(
        f"/products/{mouse['id']}"
    ).json()["stock"] == 8


def test_product_price_change_preserves_order_price(
    client,
    admin_headers,
    customer_headers,
    catalogue,
    placed_order,
):
    _, mouse = catalogue

    response = client.patch(
        f"/products/{mouse['id']}",
        headers=admin_headers,
        json={"price": "600.00"},
    )

    assert response.status_code == 200, response.text

    response = client.get(
        f"/orders/{placed_order['id']}",
        headers=customer_headers,
    )

    assert response.status_code == 200

    saved_order = response.json()

    mouse_item = next(
        item
        for item in saved_order["items"]
        if item["product_id"] == mouse["id"]
    )

    assert Decimal(mouse_item["unit_price"]) == Decimal("500.00")
    assert Decimal(saved_order["total_amount"]) == Decimal("2500.00")





@pytest.mark.parametrize(
    "invalid_case",
    ["zero_quantity", "client_price", "client_owner"],
)
def test_invalid_cart_item_requests_are_rejected(
    client,
    customer_headers,
    catalogue,
    session_factory,
    invalid_case,
):
    keyboard, _ = catalogue

    body = {
        "product_id": keyboard["id"],
        "quantity": 1,
    }

    if invalid_case == "zero_quantity":
        body["quantity"] = 0
    elif invalid_case == "client_price":
        body["unit_price"] = "1.00"
    else:
        body["user_id"] = 999

    before = database_state(session_factory)

    response = client.post(
        "/cart/items",
        headers=customer_headers,
        json=body,
    )

    assert response.status_code == 422, response.text
    assert database_state(session_factory) == before

    cart = client.get("/cart", headers=customer_headers).json()
    assert cart["items"] == []


def test_empty_cart_cannot_checkout(
    client,
    customer_headers,
    session_factory,
):
    before = database_state(session_factory)

    response = client.post(
        "/cart/checkout",
        headers={
            **customer_headers,
            "Idempotency-Key": "empty-cart-test",
        },
    )

    assert response.status_code == 409, response.text
    assert database_state(session_factory) == before


@pytest.mark.parametrize("actor", ["customer", "admin"])
def test_cancellation_preserves_history_and_restores_stock_once(
    client,
    customer_headers,
    admin_headers,
    catalogue,
    placed_order,
    actor,
):
    headers = (
        customer_headers
        if actor == "customer"
        else admin_headers
    )

    path = f"/orders/{placed_order['id']}/cancel"

    first = client.post(path, headers=headers)

    assert first.status_code == 200, first.text

    cancelled = first.json()["order"]

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None
    assert cancelled["items"] == placed_order["items"]
    assert cancelled["total_amount"] == placed_order["total_amount"]

    second = client.post(path, headers=headers)

    assert second.status_code == 200
    assert second.json()["order"]["cancelled_at"] == cancelled["cancelled_at"]

    keyboard, mouse = catalogue

    assert client.get(
        f"/products/{keyboard['id']}"
    ).json()["stock"] == 5

    assert client.get(
        f"/products/{mouse['id']}"
    ).json()["stock"] == 10

    saved = client.get(
        f"/orders/{placed_order['id']}",
        headers=customer_headers,
    )

    assert saved.status_code == 200
    assert saved.json()["status"] == "cancelled"
    assert saved.json()["items"] == placed_order["items"]


def test_order_ownership_and_listing(
    client,
    customer_headers,
    admin_headers,
    other_customer_headers,
    placed_order,
    session_factory,
):
    path = f"/orders/{placed_order['id']}"
    before = database_state(session_factory)

    response = client.get(
        "/orders",
        headers=other_customer_headers,
    )
    assert response.status_code == 200
    assert response.json() == []

    assert client.get(
        path,
        headers=other_customer_headers,
    ).status_code == 404

    assert client.post(
        f"{path}/cancel",
        headers=other_customer_headers,
    ).status_code == 404

    assert database_state(session_factory) == before

    for headers in (customer_headers, admin_headers):
        response = client.get(path, headers=headers)
        assert response.status_code == 200

        response = client.get("/orders", headers=headers)
        assert response.status_code == 200
        assert [order["id"] for order in response.json()] == [
            placed_order["id"]
        ]


@pytest.mark.parametrize("cancel_first", [False, True])
def test_product_with_order_history_cannot_be_deleted(
    client,
    admin_headers,
    customer_headers,
    catalogue,
    placed_order,
    session_factory,
    cancel_first,
):
    if cancel_first:
        response = client.post(
            f"/orders/{placed_order['id']}/cancel",
            headers=customer_headers,
        )
        assert response.status_code == 200

    before = database_state(session_factory)
    keyboard, _ = catalogue

    response = client.delete(
        f"/products/{keyboard['id']}",
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert database_state(session_factory) == before


def test_account_with_order_history_cannot_be_deleted(
    client,
    customer_headers,
    placed_order,
    session_factory,
):
    before = database_state(session_factory)

    response = client.delete(
        f"/users/{placed_order['user_id']}",
        headers=customer_headers,
    )

    assert response.status_code == 409
    assert database_state(session_factory) == before


@pytest.mark.parametrize("operation", ["create", "cancel"])
def test_commit_failure_rolls_back_order_and_stock(
    client,
    customer_headers,
    catalogue,
    placed_order,
    session_factory,
    monkeypatch,
    operation,
):
    if operation == "create":
        added = client.post(
            "/cart/items",
            headers=customer_headers,
            json={
                "product_id": catalogue[0]["id"],
                "quantity": 1,
            },
        )
        assert added.status_code == 201, added.text

    before = database_state(session_factory)

    def fail_commit(session):
        session.flush()
        raise SQLAlchemyError("Simulated commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)

        with pytest.raises(
            SQLAlchemyError,
            match="Simulated commit failure",
        ):
            if operation == "create":
                client.post(
                    "/cart/checkout",
                    headers={
                        **customer_headers,
                        "Idempotency-Key": "commit-failure-test",
                    },
                )
            else:
                client.post(
                    f"/orders/{placed_order['id']}/cancel",
                    headers=customer_headers,
                )

    assert database_state(session_factory) == before

    if operation == "create":
        cart = client.get(
            "/cart",
            headers=customer_headers,
        ).json()
        assert cart["items"][0]["quantity"] == 1


def test_inactive_customer_cannot_access_or_cancel_orders(
    client,
    customer_headers,
    placed_order,
    session_factory,
):
    with session_factory() as db:
        user = db.get(User, placed_order["user_id"])
        user.is_active = False
        db.commit()

    before = database_state(session_factory)

    assert client.get(
        "/orders",
        headers=customer_headers,
    ).status_code == 403

    assert client.post(
        f"/orders/{placed_order['id']}/cancel",
        headers=customer_headers,
    ).status_code == 403

    assert database_state(session_factory) == before