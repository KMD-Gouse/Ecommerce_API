import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Cart, CartItem, Order, Product, User
from app.security import create_access_token, hash_password


@pytest.fixture
def postgres_checkout_db():
    database_url = os.getenv("CHECKOUT_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("Set CHECKOUT_TEST_DATABASE_URL to run PostgreSQL tests")

    url = make_url(database_url)

    if (
        url.get_backend_name() != "postgresql"
        or not url.database
        or not url.database.endswith("_test")
    ):
        pytest.fail(
            "CHECKOUT_TEST_DATABASE_URL must point to a PostgreSQL "
            "database whose name ends in _test"
        )

    # Each run gets its own schema within the dedicated test database.
    schema_name = f"checkout_{uuid4().hex}"
    admin_engine = create_engine(url)

    with admin_engine.begin() as connection:
        connection.execute(
            text(f'CREATE SCHEMA "{schema_name}"')
        )

    test_engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema_name}",
        },
        pool_pre_ping=True,
    )

    def session_factory():
        return sessionmaker(bind=test_engine)()

    def override_get_db():
        with session_factory() as db:
            yield db

    try:
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db

        yield session_factory

    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()

        with admin_engine.begin() as connection:
            connection.execute(
                text(f'DROP SCHEMA "{schema_name}" CASCADE')
            )

        admin_engine.dispose()


def test_two_customers_cannot_buy_the_last_unit(postgres_checkout_db):
    session_factory = postgres_checkout_db

    # Set up two customers, each with the same product in their cart.
    with session_factory() as db:
        password_hash = hash_password("PracticePass123!")

        first_user = User(
            name="First Buyer",
            email="first@example.com",
            hashed_password=password_hash,
            role="customer",
            is_active=True,
        )
        second_user = User(
            name="Second Buyer",
            email="second@example.com",
            hashed_password=password_hash,
            role="customer",
            is_active=True,
        )
        product = Product(
            name="Last Unit",
            price=Decimal("100.00"),
            stock=1,
        )

        db.add_all([first_user, second_user, product])
        db.flush()

        first_cart = Cart(user_id=first_user.id)
        second_cart = Cart(user_id=second_user.id)
        db.add_all([first_cart, second_cart])
        db.flush()

        db.add_all([
            CartItem(
                cart_id=first_cart.id,
                product_id=product.id,
                quantity=1,
            ),
            CartItem(
                cart_id=second_cart.id,
                product_id=product.id,
                quantity=1,
            ),
        ])

        first_user_id = first_user.id
        second_user_id = second_user.id
        product_id = product.id
        db.commit()

    start_together = Barrier(3)

    def checkout(user_id: int, key: str):
        headers = {
            "Authorization": (
                f"Bearer {create_access_token(user_id)}"
            ),
            "Idempotency-Key": key,
        }

        with TestClient(app) as client:
            start_together.wait(timeout=15)
            return client.post("/cart/checkout", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            checkout,
            first_user_id,
            "first-buyer-checkout",
        )
        second = executor.submit(
            checkout,
            second_user_id,
            "second-buyer-checkout",
        )

        start_together.wait(timeout=15)

        responses = [
            first.result(timeout=30),
            second.result(timeout=30),
        ]

    assert sorted(
        response.status_code for response in responses
    ) == [201, 409], [response.text for response in responses]

    with session_factory() as db:
        assert db.get(Product, product_id).stock == 0
        assert len(db.scalars(select(Order)).all()) == 1

        # The losing customer's item remains in their cart.
        assert len(db.scalars(select(CartItem)).all()) == 1
def test_checkout_failure_rolls_back_everything(postgres_checkout_db):
    session_factory = postgres_checkout_db

    with session_factory() as db:
        user = User(
            name="Rollback Buyer",
            email="rollback@example.com",
            hashed_password=hash_password("PracticePass123!"),
            role="customer",
            is_active=True,
        )
        product = Product(
            name="Rollback Product",
            price=Decimal("50.00"),
            stock=2,
        )

        db.add_all([user, product])
        db.flush()

        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()

        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=2,
            )
        )

        user_id = user.id
        product_id = product.id
        db.commit()

    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}",
        "Idempotency-Key": "rollback-test-001",
    }

    def fail_after_checkout_sql(session, flush_context):
        if any(isinstance(obj, Order) for obj in session.new):
            raise RuntimeError("Simulated failure before commit")

    event.listen(Session, "after_flush", fail_after_checkout_sql)

    try:
        # TestClient propagates the deliberately raised server error.
        with TestClient(app) as client:
            with pytest.raises(
                RuntimeError,
                match="Simulated failure before commit",
            ):
                client.post("/cart/checkout", headers=headers)
    finally:
        # Always remove the simulated failure, even if the test fails.
        event.remove(
            Session,
            "after_flush",
            fail_after_checkout_sql,
        )

    with session_factory() as db:
        assert db.get(Product, product_id).stock == 2
        assert db.scalars(select(Order)).all() == []

        cart_items = db.scalars(select(CartItem)).all()
        assert len(cart_items) == 1
        assert cart_items[0].quantity == 2

    # The failed attempt did not consume the idempotency key.
    with TestClient(app) as client:
        retry = client.post("/cart/checkout", headers=headers)

    assert retry.status_code == 201, retry.text

    with session_factory() as db:
        assert db.get(Product, product_id).stock == 0
        assert len(db.scalars(select(Order)).all()) == 1
        assert db.scalars(select(CartItem)).all() == []    
def test_simultaneous_retry_creates_only_one_order(postgres_checkout_db):
    session_factory = postgres_checkout_db

    with session_factory() as db:
        user = User(
            name="Retry Buyer",
            email="retry@example.com",
            hashed_password=hash_password("PracticePass123!"),
            role="customer",
            is_active=True,
        )
        product = Product(
            name="Retry Product",
            price=Decimal("75.00"),
            stock=2,
        )

        db.add_all([user, product])
        db.flush()

        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()

        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=1,
            )
        )

        user_id = user.id
        product_id = product.id
        db.commit()

    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}",
        "Idempotency-Key": "simultaneous-retry-001",
    }
    start_together = Barrier(3)

    def send_checkout():
        with TestClient(app) as client:
            start_together.wait(timeout=15)
            return client.post("/cart/checkout", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(send_checkout)
        second = executor.submit(send_checkout)

        start_together.wait(timeout=15)

        responses = [
            first.result(timeout=30),
            second.result(timeout=30),
        ]

    assert [response.status_code for response in responses] == [
        201,
        201,
    ], [response.text for response in responses]

    order_ids = [
        response.json()["order"]["id"]
        for response in responses
    ]
    assert order_ids[0] == order_ids[1]

    with session_factory() as db:
        assert len(db.scalars(select(Order)).all()) == 1
        assert db.get(Product, product_id).stock == 1
        assert db.scalars(select(CartItem)).all() == []            
def test_simultaneous_cancellation_restores_stock_once(
    postgres_checkout_db,
):
    session_factory = postgres_checkout_db

    with session_factory() as db:
        user = User(
            name="Cancellation Buyer",
            email="cancellation@example.com",
            hashed_password=hash_password("PracticePass123!"),
            role="customer",
            is_active=True,
        )
        product = Product(
            name="Cancellation Product",
            price=Decimal("100.00"),
            stock=1,
        )

        db.add_all([user, product])
        db.flush()

        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()

        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=1,
            )
        )

        user_id = user.id
        product_id = product.id
        db.commit()

    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}",
    }

    with TestClient(app) as client:
        checkout = client.post(
            "/cart/checkout",
            headers={
                **headers,
                "Idempotency-Key": "cancellation-test-001",
            },
        )

    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["order"]["id"]

    start_together = Barrier(3)

    def cancel_order():
        with TestClient(app) as client:
            start_together.wait(timeout=15)
            return client.post(
                f"/orders/{order_id}/cancel",
                headers=headers,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cancel_order)
        second = executor.submit(cancel_order)

        start_together.wait(timeout=15)

        responses = [
            first.result(timeout=30),
            second.result(timeout=30),
        ]

    assert all(
        response.status_code == 200
        for response in responses
    ), [response.text for response in responses]

    with session_factory() as db:
        saved_order = db.get(Order, order_id)

        assert saved_order.status == "cancelled"
        assert saved_order.cancelled_at is not None
        assert len(saved_order.items) == 1
        assert saved_order.items[0].unit_price == Decimal("100.00")

        # Original stock was 1. Restoring it twice would make this 2.
        assert db.get(Product, product_id).stock == 1        