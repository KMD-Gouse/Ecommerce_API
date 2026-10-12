from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings


@pytest.fixture
def authenticated_user(client):
    registration = client.post(
        "/users",
        json={
            "name": "Profile Test",
            "email": "profile@example.com",
            "password": "PracticePass123!",
        },
    )

    assert registration.status_code == 201, registration.text

    login = client.post(
        "/auth/login",
        data={
            "username": "profile@example.com",
            "password": "PracticePass123!",
        },
    )

    assert login.status_code == 200, login.text

    return {
        "user": registration.json(),
        "token": login.json()["access_token"],
    }


def test_me_returns_current_user(client, authenticated_user):
    response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == authenticated_user["user"]["id"]
    assert data["email"] == "profile@example.com"
    assert data["role"] == "customer"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data


def test_me_rejects_missing_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401, response.text


def test_me_rejects_invalid_token(client):
    response = client.get(
        "/users/me",
        headers={
            "Authorization": "Bearer this-is-not-a-valid-jwt",
        },
    )

    assert response.status_code == 401, response.text


def test_me_rejects_expired_token(client, authenticated_user):
    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": str(authenticated_user["user"]["id"]),
            "iat": now - timedelta(minutes=60),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )

    response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {expired_token}",
        },
    )

    assert response.status_code == 401, response.text