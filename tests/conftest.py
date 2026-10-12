import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture
def session_factory(tmp_path):
    database_path = tmp_path / "test.db"

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestSession = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    try:
        yield TestSession
    finally:
        engine.dispose()


@pytest.fixture
def client(session_factory):
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def create_login_headers(client, session_factory, role):
    email = f"{role}@example.com"
    password = "PracticePass123!"

    # Set up the account directly in the temporary test database.
    with session_factory() as db:
        user = User(
            name=f"Test {role}",
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()

    # Exercise the real login endpoint.
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture
def admin_headers(client, session_factory):
    return create_login_headers(
        client,
        session_factory,
        role="admin",
    )


@pytest.fixture
def customer_headers(client, session_factory):
    return create_login_headers(
        client,
        session_factory,
        role="customer",
    )