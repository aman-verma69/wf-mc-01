import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Base
from backend.main import app
from backend.database.session import get_db


@pytest.fixture(autouse=True)
def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()


def test_customer_cart_lifecycle(test_db):
    client = TestClient(app)

    response = client.post(
        "/api/v1/customers/cust-1/cart/items",
        json={
            "product_id": "prod-1",
            "name": "Sony WH-CH520",
            "quantity": 1,
            "unit_price_paise": 3990,
            "currency": "INR",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["customer_id"] == "cust-1"
    assert data["total_paise"] == 3990

    response = client.get("/api/v1/customers/cust-1/cart")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"][0]["product_id"] == "prod-1"
    assert payload["items"][0]["quantity"] == 1

    response = client.patch(
        "/api/v1/customers/cust-1/cart/items/prod-1",
        json={"quantity": 2},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_paise"] == 7980

    response = client.delete("/api/v1/customers/cust-1/cart/items/prod-1")
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_checkout_uses_persisted_customer_cart_and_customer_isolation(test_db):
    client = TestClient(app)

    client.post(
        "/api/v1/customers/cust-1/cart/items",
        json={
            "product_id": "prod-1",
            "name": "Sony WH-CH520",
            "quantity": 1,
            "unit_price_paise": 2500,
            "currency": "INR",
        },
    )
    client.post(
        "/api/v1/customers/cust-2/cart/items",
        json={
            "product_id": "prod-2",
            "name": "BoAt Rockerz 450",
            "quantity": 1,
            "unit_price_paise": 4990,
            "currency": "INR",
        },
    )

    response = client.post(
        "/api/v1/checkout/initiate",
        json={"customer_id": "cust-1"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["customer_id"] == "cust-1"
    assert payload["amount_paise"] == 2500

    response = client.get("/api/v1/customers/cust-1/orders")
    assert response.status_code == 200, response.text
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["customer_id"] == "cust-1"

    response = client.get("/api/v1/customers/cust-2/orders")
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_order_and_refund_authorization_checks(test_db):
    client = TestClient(app)

    client.post(
        "/api/v1/customers/cust-1/cart/items",
        json={
            "product_id": "prod-1",
            "name": "Sony WH-CH520",
            "quantity": 1,
            "unit_price_paise": 2500,
            "currency": "INR",
        },
    )

    checkout = client.post("/api/v1/checkout/initiate", json={"customer_id": "cust-1"})
    order_id = checkout.json()["order_id"]

    response = client.get(f"/api/v1/orders/{order_id}")
    assert response.status_code == 200, response.text
    assert response.json()["customer_id"] == "cust-1"

    response = client.get(f"/api/v1/customers/cust-2/orders")
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = client.post(f"/api/v1/orders/{order_id}/cancel", json={"customer_id": "cust-1"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    response = client.post(f"/api/v1/orders/{order_id}/cancel", json={"customer_id": "cust-1"})
    assert response.status_code == 400, response.text
