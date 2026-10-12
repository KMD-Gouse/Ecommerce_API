import jwt

from app.core.config import settings


def register_user(client):
    response = client.post(
        "/users",
        json={
            "name": "Auth Test",
            "email": "auth@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def test_login_returns_valid_token(client):
    user = register_user(client)

    response = client.post(
        "/auth/login",
        data={
            "username": "auth@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["token_type"] == "bearer"

    payload = jwt.decode(
        data["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )

    assert payload["sub"] == str(user["id"])

    assert payload["exp"] - payload["iat"] == (
        settings.access_token_expire_minutes * 60
    )


def test_login_rejects_wrong_password(client):
    register_user(client)

    response = client.post(
        "/auth/login",
        data={
            "username": "auth@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Incorrect email or password"
    assert "access_token" not in response.json()


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "missing@example.com",
            "password": "PracticePass123!",
        },
    )

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Incorrect email or password"
    assert "access_token" not in response.json()