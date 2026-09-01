import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Base, Customer, InventoryReservation, Order, OrderStatus, Product
from backend.database.session import get_db
from backend.main import app
from backend.services.payment_service import handle_payment_captured, handle_payment_failed


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


def register(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery"})
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "correct horse battery"})
    return response.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


def make_merchant(test_db, email: str) -> tuple[str, dict[str, str]]:
    client = TestClient(app)
    merchant_id, headers = register(client, email)

    async def promote():
        async with test_db() as session:
            customer = await session.get(Customer, merchant_id)
            customer.role = "merchant"
            await session.commit()

    asyncio.run(promote())
    return merchant_id, headers


def test_merchant_catalog_ownership_and_customer_protection(test_db):
    client = TestClient(app)
    merchant_id, merchant_headers = make_merchant(test_db, "merchant-catalog@example.com")
    _, other_headers = register(client, "other-merchant@example.com")
    _, customer_headers = register(client, "catalog-customer@example.com")

    created = client.post("/api/v1/products", headers=merchant_headers, json={"sku": "SKU-1", "name": "Trusted Headphones", "price_paise": 4999, "initial_stock": 2})
    assert created.status_code == 201
    product = created.json()
    assert product["merchant_id"] == merchant_id
    assert product["available_quantity"] == 2
    assert "password_hash" not in product

    assert client.patch(f"/api/v1/products/{product['id']}", headers=other_headers, json={"price_paise": 1}).status_code == 403
    assert client.patch(f"/api/v1/products/{product['id']}/inventory", headers=customer_headers, json={"add_quantity": 1}).status_code == 403
    assert client.post("/api/v1/products", headers=customer_headers, json={"sku": "SKU-2", "name": "Nope", "price_paise": 100}).status_code == 403

    duplicate = client.post("/api/v1/products", headers=merchant_headers, json={"sku": "SKU-1", "name": "Duplicate", "price_paise": 100})
    assert duplicate.status_code == 409


def test_catalog_cart_ignores_client_price_and_checkout_reserves_stock(test_db):
    client = TestClient(app)
    _, merchant_headers = make_merchant(test_db, "merchant-trusted@example.com")
    customer_id, customer_headers = register(client, "trusted-customer@example.com")
    product = client.post("/api/v1/products", headers=merchant_headers, json={"sku": "SKU-TRUSTED", "name": "Trusted Product", "price_paise": 7000, "initial_stock": 1}).json()

    added = client.post(f"/api/v1/customers/{customer_id}/cart/items", headers=customer_headers, json={"product_id": product["id"], "name": "Fake", "quantity": 1, "unit_price_paise": 1})
    assert added.status_code == 200
    assert added.json()["items"][0]["unit_price_paise"] == 7000

    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_catalog_order"}):
        checkout = client.post("/api/v1/checkout/initiate", headers={**customer_headers, "Idempotency-Key": "catalog-checkout"}, json={})
    assert checkout.status_code == 200
    assert checkout.json()["amount_paise"] == 7000

    async def read_state():
        async with test_db() as session:
            item = await session.get(Product, product["id"])
            reservation = await session.scalar(__import__("sqlalchemy").select(InventoryReservation).where(InventoryReservation.order_id == checkout.json()["order_id"]))
            return item.physical_quantity, item.reserved_quantity, reservation.status

    assert asyncio.run(read_state()) == (1, 1, "reserved")


def test_stock_cannot_be_oversold_and_capture_finalizes_once(test_db):
    client = TestClient(app)
    _, merchant_headers = make_merchant(test_db, "merchant-stock@example.com")
    customer_a, headers_a = register(client, "stock-a@example.com")
    customer_b, headers_b = register(client, "stock-b@example.com")
    product = client.post("/api/v1/products", headers=merchant_headers, json={"sku": "SKU-STOCK", "name": "One Item", "price_paise": 1000, "initial_stock": 1}).json()
    for customer_id, headers in ((customer_a, headers_a), (customer_b, headers_b)):
        assert client.post(f"/api/v1/customers/{customer_id}/cart/items", headers=headers, json={"product_id": product["id"], "name": "One Item", "quantity": 1}).status_code == 200

    with patch("backend.services.checkout_service.create_order", side_effect=[{"id": "rp-stock-a"}, {"id": "rp-stock-b"}]):
        first = client.post("/api/v1/checkout/initiate", headers=headers_a, json={})
        second = client.post("/api/v1/checkout/initiate", headers=headers_b, json={})
    assert first.status_code == 200
    assert second.status_code == 400

    async def capture_twice():
        async with test_db() as session:
            entity = {"id": "pay-stock", "order_id": "rp-stock-a", "amount": 1000}
            await handle_payment_captured(session, entity)
            await handle_payment_captured(session, entity)
            item = await session.get(Product, product["id"])
            return item.physical_quantity, item.reserved_quantity

    assert asyncio.run(capture_twice()) == (0, 0)


def test_payment_failure_and_cancel_release_reservation(test_db):
    client = TestClient(app)
    _, merchant_headers = make_merchant(test_db, "merchant-release@example.com")
    customer_id, headers = register(client, "release@example.com")
    product = client.post("/api/v1/products", headers=merchant_headers, json={"sku": "SKU-RELEASE", "name": "Release Item", "price_paise": 1500, "initial_stock": 2}).json()
    client.post(f"/api/v1/customers/{customer_id}/cart/items", headers=headers, json={"product_id": product["id"], "name": "Release Item", "quantity": 1})
    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp-release"}):
        checkout = client.post("/api/v1/checkout/initiate", headers=headers, json={})
    order_id = checkout.json()["order_id"]

    async def fail():
        async with test_db() as session:
            await handle_payment_failed(session, {"order_id": "rp-release"})
            item = await session.get(Product, product["id"])
            return item.reserved_quantity

    assert asyncio.run(fail()) == 0
    cancelled = client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers, json={})
    assert cancelled.status_code == 200