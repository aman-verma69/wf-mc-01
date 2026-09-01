import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Base, Order, OrderStatus, Payment, PaymentStatus
from backend.services.payment_service import handle_payment_captured
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


def _register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery"})
    assert registered.status_code == 201, registered.text
    customer_id = registered.json()["id"]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "correct horse battery"})
    assert login.status_code == 200, login.text
    return customer_id, login.json()["access_token"]


def test_customer_cart_lifecycle(test_db):
    client = TestClient(app)
    customer_id, token = _register_and_login(client, "lifecycle@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/api/v1/customers/{customer_id}/cart/items",
        headers=headers,
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
    assert data["customer_id"] == customer_id
    assert data["total_paise"] == 3990

    response = client.get(f"/api/v1/customers/{customer_id}/cart", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"][0]["product_id"] == "prod-1"
    assert payload["items"][0]["quantity"] == 1

    response = client.patch(
        f"/api/v1/customers/{customer_id}/cart/items/prod-1",
        headers=headers,
        json={"quantity": 2},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_paise"] == 7980

    response = client.delete(f"/api/v1/customers/{customer_id}/cart/items/prod-1", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_checkout_uses_persisted_customer_cart_and_customer_isolation(test_db):
    client = TestClient(app)
    customer_one, token_one = _register_and_login(client, "checkout-one@example.com")
    customer_two, token_two = _register_and_login(client, "checkout-two@example.com")
    headers_one = {"Authorization": f"Bearer {token_one}"}
    headers_two = {"Authorization": f"Bearer {token_two}"}

    client.post(
        f"/api/v1/customers/{customer_one}/cart/items",
        headers=headers_one,
        json={
            "product_id": "prod-1",
            "name": "Sony WH-CH520",
            "quantity": 1,
            "unit_price_paise": 2500,
            "currency": "INR",
        },
    )
    client.post(
        f"/api/v1/customers/{customer_two}/cart/items",
        headers=headers_two,
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
        headers=headers_one,
        json={"customer_id": customer_one},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["customer_id"] == customer_one
    assert payload["amount_paise"] == 2500

    response = client.get(f"/api/v1/customers/{customer_one}/orders", headers=headers_one)
    assert response.status_code == 200, response.text
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["customer_id"] == customer_one

    response = client.get(f"/api/v1/customers/{customer_two}/orders", headers=headers_two)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_order_and_refund_authorization_checks(test_db):
    client = TestClient(app)
    customer_id, token = _register_and_login(client, "orders@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        f"/api/v1/customers/{customer_id}/cart/items",
        headers=headers,
        json={
            "product_id": "prod-1",
            "name": "Sony WH-CH520",
            "quantity": 1,
            "unit_price_paise": 2500,
            "currency": "INR",
        },
    )

    checkout = client.post("/api/v1/checkout/initiate", headers=headers, json={"customer_id": customer_id})
    order_id = checkout.json()["order_id"]

    response = client.get(f"/api/v1/orders/{order_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["customer_id"] == customer_id

    response = client.get("/api/v1/customers/cust-2/orders", headers=headers)
    assert response.status_code == 403, response.text

    response = client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers, json={"customer_id": customer_id})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    response = client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers, json={"customer_id": customer_id})
    assert response.status_code == 400, response.text

def test_payment_captured_transitions_created_order_to_paid(test_db):
    async def run_test():
        async with test_db() as session:
            # Create a local order in CREATED state.
            order = Order(
                id="order-created-to-paid-1",
                customer_id="cust-payment-1",
                amount_paise=659800,
                currency="INR",
                status=OrderStatus.CREATED,
                razorpay_order_id="order_test_created_paid_001",
                cart_snapshot={
                    "customer_id": "cust-payment-1",
                    "items": [
                        {
                            "product_id": "prod-1",
                            "name": "Test Gaming Headphones",
                            "quantity": 2,
                            "unit_price_paise": 329900,
                            "currency": "INR",
                        }
                    ],
                },
            )

            session.add(order)
            await session.commit()

            # Simulate a Razorpay payment.captured event.
            entity = {
                "id": "pay_test_created_paid_001",
                "order_id": "order_test_created_paid_001",
                "amount": 659800,
                "method": "card",
            }

            await handle_payment_captured(session, entity)

            # Verify the order transitioned from CREATED to PAID.
            await session.refresh(order)

            payment = await session.scalar(
                select(Payment).where(
                    Payment.razorpay_payment_id == "pay_test_created_paid_001"
                )
            )

            assert order.status == OrderStatus.PAID
            assert payment is not None
            assert payment.status == PaymentStatus.CAPTURED
            assert payment.order_id == order.id
            assert payment.amount_paise == 659800

    asyncio.run(run_test())
