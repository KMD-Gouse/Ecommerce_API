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

@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/users", None),
        ("get", "/users/1", None),
        ("patch", "/users/1", {"name": "Changed"}),
        ("delete", "/users/1", None),
        ("get", "/orders", None),
        ("get", "/orders/1", None),
        ("post", "/cart/checkout", None),
        ("post", "/orders/1/cancel", None),
    ],
)
def test_anonymous_access_denied(client, method, path, body):
    headers = (
        {"Idempotency-Key": "anonymous-checkout-test"}
        if path == "/cart/checkout"
        else {}
    )

    response = client.request(
        method,
        path,
        json=body,
        headers=headers,
    )

    assert response.status_code == 401


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














