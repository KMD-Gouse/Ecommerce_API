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


def create_product(client, admin_headers, stock=2):
    response = client.post(
        "/products",
        headers=admin_headers,
        json={
            "name": "Wireless Mouse",
            "price": "499.00",
            "stock": stock,
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


# 1. A product must have a price.
def test_product_requires_price(client, admin_headers):
    response = client.post(
        "/products",
        headers=admin_headers,
        json={
            "name": "Wireless Mouse",
            "stock": 2,
        },
    )

    assert response.status_code == 422, response.text


# 2. Stock cannot be negative.
def test_negative_stock_is_rejected(client, admin_headers):
    response = client.post(
        "/products",
        headers=admin_headers,
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
def test_duplicate_email_returns_409(client, admin_headers):
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

    users_response = client.get("/users", headers=admin_headers)

    assert users_response.status_code == 200
    assert len(users_response.json()) == 2


def test_home_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "E-Commerce API"}


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_about_endpoint(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert response.json() == {"project": "Mini E-Commerce API"}






