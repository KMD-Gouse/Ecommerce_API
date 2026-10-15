import pytest


@pytest.fixture
def catalogue_with_categories(client, admin_headers):
    categories = {}

    for name in ("Electronics", "Office"):
        response = client.post(
            "/categories",
            headers=admin_headers,
            json={"name": name},
        )
        assert response.status_code == 201, response.text
        categories[name] = response.json()["id"]

    products = []

    for data in (
        {
            "name": "Mechanical Keyboard",
            "price": "1500.00",
            "stock": 5,
            "category_id": categories["Electronics"],
        },
        {
            "name": "Wireless Mouse",
            "price": "500.00",
            "stock": 10,
            "category_id": categories["Electronics"],
        },
        {
            "name": "Mouse Pad",
            "price": "250.00",
            "stock": 20,
            "category_id": categories["Office"],
        },
    ):
        response = client.post(
            "/products",
            headers=admin_headers,
            json=data,
        )
        assert response.status_code == 201, response.text
        products.append(response.json())

    return categories, products


def test_search_ignores_case(
    client,
    catalogue_with_categories,
):
    _, products = catalogue_with_categories

    response = client.get(
        "/products",
        params={"search": "mOuSe"},
    )

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [
        products[1]["id"],
        products[2]["id"],
    ]


def test_combined_category_and_price_filters(
    client,
    catalogue_with_categories,
):
    categories, products = catalogue_with_categories

    response = client.get(
        "/products",
        params={
            "category_id": categories["Electronics"],
            "min_price": "300.00",
            "max_price": "600.00",
        },
    )

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [
        products[1]["id"]
    ]


def test_pagination_has_stable_order(
    client,
    catalogue_with_categories,
):
    _, products = catalogue_with_categories

    first_page = client.get(
        "/products",
        params={"limit": 2, "offset": 0},
    )

    second_page = client.get(
        "/products",
        params={"limit": 2, "offset": 2},
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json() == products[:2]
    assert second_page.json() == products[2:]


def test_search_treats_percent_as_text(
    client,
    catalogue_with_categories,
):
    response = client.get(
        "/products",
        params={"search": "%"},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"category_id": 0},
        {"search": "   "},
        {"min_price": "700", "max_price": "200"},
    ],
)
def test_invalid_catalogue_queries(
    client,
    catalogue_with_categories,
    params,
):
    response = client.get(
        "/products",
        params=params,
    )

    assert response.status_code == 422