def create_user(client):
    response = client.post(
        "/users",
        json={
            "name": "Gouse",
            "email": "gouse@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert "password" not in data
    assert "hashed_password" not in data

    return data


def create_product(client, stock=2):
    response = client.post(
        "/products",
        json={
            "name": "Wireless Mouse",
            "price": "499.00",
            "stock": stock,
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


# 1. A product must have a price.
def test_product_requires_price(client):
    response = client.post(
        "/products",
        json={
            "name": "Wireless Mouse",
            "stock": 2,
        },
    )

    assert response.status_code == 422, response.text


# 2. Stock cannot be negative.
def test_negative_stock_is_rejected(client):
    response = client.post(
        "/products",
        json={
            "name": "Wireless Mouse",
            "price": "499.00",
            "stock": -1,
        },
    )

    assert response.status_code == 422, response.text


# 3. A nonexistent product should return 404.
def test_missing_product_returns_404(client):
    response = client.get("/products/999")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Product not found"


# 4. Two users cannot register with the same email.
def test_duplicate_email_returns_409(client):
    create_user(client)

    response = client.post(
        "/users",
        json={
            "name": "Another User",
            "email": "gouse@example.com",
            "password": "PracticePass456!",
        },
    )

    assert response.status_code == 409, response.text

    users_response = client.get("/users")

    assert users_response.status_code == 200
    assert len(users_response.json()) == 1


# 5. Creating an order should reduce stock.
def test_order_creation_reduces_stock(client):
    user = create_user(client)
    product = create_product(client, stock=2)

    response = client.post(
        "/orders",
        json={
            "user_id": user["id"],
            "product_id": product["id"],
            "quantity": 1,
        },
    )

    assert response.status_code == 201, response.text

    product_response = client.get(
        f"/products/{product['id']}"
    )

    assert product_response.status_code == 200
    assert product_response.json()["stock"] == 1

    orders_response = client.get("/orders")

    assert orders_response.status_code == 200
    assert len(orders_response.json()) == 1


# 6. Insufficient stock must not create an order.
def test_insufficient_stock_leaves_data_unchanged(client):
    user = create_user(client)
    product = create_product(client, stock=1)

    response = client.post(
        "/orders",
        json={
            "user_id": user["id"],
            "product_id": product["id"],
            "quantity": 2,
        },
    )

    assert response.status_code == 409, response.text

    product_response = client.get(
        f"/products/{product['id']}"
    )

    assert product_response.status_code == 200
    assert product_response.json()["stock"] == 1

    orders_response = client.get("/orders")

    assert orders_response.status_code == 200
    assert orders_response.json() == []


# 7. Cancelling twice must not restore stock twice.
def test_order_cancellation_restores_stock(client):
    user = create_user(client)
    product = create_product(client, stock=2)

    response = client.post(
        "/orders",
        json={
            "user_id": user["id"],
            "product_id": product["id"],
            "quantity": 1,
        },
    )

    assert response.status_code == 201, response.text

    order_id = response.json()["order"]["id"]

    response = client.delete(f"/orders/{order_id}")

    assert response.status_code == 200, response.text

    product_response = client.get(
        f"/products/{product['id']}"
    )

    assert product_response.status_code == 200
    assert product_response.json()["stock"] == 2

    # Try cancelling the same order again.
    response = client.delete(f"/orders/{order_id}")

    assert response.status_code == 404, response.text

    product_response = client.get(
        f"/products/{product['id']}"
    )

    assert product_response.status_code == 200
    assert product_response.json()["stock"] == 2


# 8. A product referenced by an order cannot be deleted.
def test_product_with_order_cannot_be_deleted(client):
    user = create_user(client)
    product = create_product(client)

    response = client.post(
        "/orders",
        json={
            "user_id": user["id"],
            "product_id": product["id"],
            "quantity": 1,
        },
    )

    assert response.status_code == 201, response.text

    response = client.delete(
        f"/products/{product['id']}"
    )

    assert response.status_code == 409, response.text

    response = client.get(
        f"/products/{product['id']}"
    )

    assert response.status_code == 200, response.text