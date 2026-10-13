import pytest
from sqlalchemy import select
from app.models import Order, Product, User


@pytest.fixture
def accounts(client, admin_headers, customer_headers):
    response = client.post('/users', json={
        'name': 'Other Customer', 'email': 'other@example.com',
        'password': 'PracticePass123!',
    })
    assert response.status_code == 201
    token = client.post('/auth/login', data={
        'username': 'other@example.com', 'password': 'PracticePass123!',
    }).json()['access_token']
    other = {'Authorization': f'Bearer {token}'}
    return {
        'admin': admin_headers, 'customer': customer_headers, 'other': other,
        'customer_id': client.get('/users/me', headers=customer_headers).json()['id'],
        'other_id': response.json()['id'],
    }


@pytest.fixture
def purchase(client, accounts):
    product = client.post('/products', headers=accounts['admin'], json={
        'name': 'Mouse', 'price': '499.00', 'stock': 5,
    }).json()
    response = client.post('/orders', headers=accounts['customer'], json={
        'product_id': product['id'], 'quantity': 2,
    })
    assert response.status_code == 201, response.text
    return response.json()['order'], product


@pytest.mark.parametrize('method,path,body', [
    ('get', '/users', None), ('get', '/users/1', None),
    ('patch', '/users/1', {'name': 'Changed'}), ('delete', '/users/1', None),
    ('get', '/orders', None), ('get', '/orders/1', None),
    ('post', '/orders', {'product_id': 1, 'quantity': 1}),
    ('patch', '/orders/1', {'quantity': 2}), ('delete', '/orders/1', None),
])
def test_anonymous_access_denied(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize('method,body', [
    ('get', None), ('patch', {'name': 'Hacked', 'email': 'hacked@example.com'}),
    ('delete', None),
])
def test_other_profile_denied_without_changes(client, accounts, session_factory, method, body):
    user_id = accounts['other_id']
    response = client.request(method, f'/users/{user_id}', headers=accounts['customer'], json=body)
    assert response.status_code == 403
    with session_factory() as db:
        saved = db.get(User, user_id)
        assert saved.name == 'Other Customer'
        assert saved.email == 'other@example.com'


def test_profile_owner_and_admin(client, accounts):
    uid = accounts['customer_id']
    assert client.get('/users', headers=accounts['customer']).status_code == 403
    assert client.get('/users', headers=accounts['admin']).status_code == 200
    assert client.get(f'/users/{uid}', headers=accounts['customer']).status_code == 200
    response = client.patch(f'/users/{uid}', headers=accounts['customer'], json={'name': 'My Profile'})
    assert response.status_code == 200
    assert response.json()['name'] == 'My Profile'
    assert client.get(f'/users/{uid}', headers=accounts['admin']).status_code == 200
    assert client.patch(f'/users/{uid}', headers=accounts['admin'], json={'name': 'Admin Edit'}).status_code == 200
    assert client.delete(f'/users/{uid}', headers=accounts['admin']).status_code == 200
    assert client.get('/users/me', headers=accounts['customer']).status_code == 401


def test_customer_can_delete_own_account(client, accounts):
    assert client.delete(f"/users/{accounts['other_id']}", headers=accounts['other']).status_code == 200


@pytest.mark.parametrize('method,body', [('get', None), ('patch', {'quantity': 4}), ('delete', None)])
def test_other_order_hidden_without_changes(client, accounts, purchase, session_factory, method, body):
    order, product = purchase
    response = client.request(method, f"/orders/{order['id']}", headers=accounts['other'], json=body)
    assert response.status_code == 404
    with session_factory() as db:
        assert db.get(Order, order['id']).quantity == 2
        assert db.get(Product, product['id']).stock == 3


def test_order_identity_listing_update_and_cancel(client, accounts, purchase):
    order, product = purchase
    assert order['user_id'] == accounts['customer_id']
    assert client.get('/orders', headers=accounts['other']).json() == []
    assert client.get('/orders', headers=accounts['customer']).json() == [order]
    assert client.get('/orders', headers=accounts['admin']).json() == [order]
    path = f"/orders/{order['id']}"
    assert client.get(path, headers=accounts['customer']).status_code == 200
    assert client.patch(path, headers=accounts['customer'], json={'quantity': 3}).status_code == 200
    assert client.get(f"/products/{product['id']}").json()['stock'] == 2
    assert client.delete(path, headers=accounts['customer']).status_code == 200
    assert client.delete(path, headers=accounts['customer']).status_code == 404
    assert client.get(f"/products/{product['id']}").json()['stock'] == 5


def test_admin_can_manage_customer_order(client, accounts, purchase):
    order, _ = purchase
    path = f"/orders/{order['id']}"
    assert client.get(path, headers=accounts['admin']).status_code == 200
    assert client.patch(path, headers=accounts['admin'], json={'quantity': 1}).status_code == 200
    assert client.delete(path, headers=accounts['admin']).status_code == 200


def test_spoofed_order_owner_rejected(client, accounts, purchase, session_factory):
    order, product = purchase
    response = client.post('/orders', headers=accounts['customer'], json={
        'user_id': accounts['other_id'], 'product_id': product['id'], 'quantity': 1,
    })
    assert response.status_code == 422
    with session_factory() as db:
        assert len(db.scalars(select(Order)).all()) == 1
        assert db.get(Product, product['id']).stock == 3


def test_failed_quantity_change_preserves_state(client, accounts, purchase, session_factory):
    order, product = purchase
    assert client.patch(f"/orders/{order['id']}", headers=accounts['customer'], json={'quantity': 99}).status_code == 409
    with session_factory() as db:
        assert db.get(Order, order['id']).quantity == 2
        assert db.get(Product, product['id']).stock == 3


def test_failed_commit_rolls_back_order_and_stock(client, accounts, purchase, session_factory, monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import SQLAlchemyError
    _, product = purchase

    def fail_commit(session):
        session.flush()  # Exercise rollback after SQL has actually been sent.
        raise SQLAlchemyError('simulated commit failure')

    with monkeypatch.context() as patch:
        patch.setattr(Session, 'commit', fail_commit)
        with pytest.raises(SQLAlchemyError):
            client.post('/orders', headers=accounts['customer'], json={'product_id': product['id'], 'quantity': 1})
    with session_factory() as db:
        assert len(db.scalars(select(Order)).all()) == 1
        assert db.get(Product, product['id']).stock == 3


def test_inactive_customer_blocked(client, accounts, purchase, session_factory):
    order, product = purchase
    with session_factory() as db:
        db.get(User, accounts['customer_id']).is_active = False
        db.commit()
    assert client.get('/users/me', headers=accounts['customer']).status_code == 403
    assert client.get('/orders', headers=accounts['customer']).status_code == 403
    assert client.delete(f"/orders/{order['id']}", headers=accounts['customer']).status_code == 403
    with session_factory() as db:
        assert db.get(Order, order['id']) is not None
        assert db.get(Product, product['id']).stock == 3
