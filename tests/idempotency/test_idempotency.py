import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Base, Order, OrderStatus, Payment, PaymentStatus
from backend.database.session import get_db
from backend.main import app


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


def customer_session(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery"})
    assert registered.status_code == 201
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "correct horse battery"})
    token = logged_in.json()["access_token"]
    return registered.json()["id"], {"Authorization": f"Bearer {token}"}


def add_cart_item(client: TestClient, customer_id: str, headers: dict[str, str], amount_paise: int = 2500) -> None:
    response = client.post(
        f"/api/v1/customers/{customer_id}/cart/items",
        headers=headers,
        json={"product_id": "prod-1", "name": "Headphones", "quantity": 1, "unit_price_paise": amount_paise},
    )
    assert response.status_code == 200


def test_checkout_replay_creates_one_local_and_razorpay_order():
    client = TestClient(app)
    customer_id, headers = customer_session(client, "checkout-idempotent@example.com")
    add_cart_item(client, customer_id, headers)
    razorpay_order = {"id": "rp_order_1", "amount": 2500, "currency": "INR"}

    with patch("backend.services.checkout_service.create_order", return_value=razorpay_order) as create_order:
        first = client.post("/api/v1/checkout/initiate", headers={**headers, "Idempotency-Key": "checkout-key-1"}, json={"customer_id": customer_id})
        replay = client.post("/api/v1/checkout/initiate", headers={**headers, "Idempotency-Key": "checkout-key-1"}, json={"customer_id": customer_id})

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.json() == first.json()
    assert create_order.call_count == 1
    assert len(client.get(f"/api/v1/customers/{customer_id}/orders", headers=headers).json()) == 1


def test_same_key_different_checkout_request_and_customer_is_rejected():
    client = TestClient(app)
    customer_a, headers_a = customer_session(client, "checkout-conflict-a@example.com")
    customer_b, headers_b = customer_session(client, "checkout-conflict-b@example.com")
    add_cart_item(client, customer_a, headers_a)
    add_cart_item(client, customer_b, headers_b)

    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_order_conflict"}):
        first = client.post("/api/v1/checkout/initiate", headers={**headers_a, "Idempotency-Key": "shared-key"}, json={"customer_id": customer_a, "actor": "api"})
        different_payload = client.post("/api/v1/checkout/initiate", headers={**headers_a, "Idempotency-Key": "shared-key"}, json={"customer_id": customer_a, "actor": "different-actor"})
        other_customer = client.post("/api/v1/checkout/initiate", headers={**headers_b, "Idempotency-Key": "shared-key"}, json={"customer_id": customer_b})

    assert first.status_code == 200
    assert different_payload.status_code == 409
    assert other_customer.status_code == 409


def test_confirmation_replay_creates_one_razorpay_order():
    client = TestClient(app)
    customer_id, headers = customer_session(client, "confirm-idempotent@example.com")
    add_cart_item(client, customer_id, headers, amount_paise=600000)

    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_pending"}):
        pending = client.post("/api/v1/checkout/initiate", headers=headers, json={"customer_id": customer_id})
    assert pending.status_code == 202

    # Force the guardrail path without depending on the configured limit.
    if pending.status_code == 200:
        pytest.fail("Expected confirmation workflow for this test")

    order_id = pending.json()["detail"]["order_id"]
    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_confirmed"}) as create_order:
        first = client.post("/api/v1/checkout/confirm", headers={**headers, "Idempotency-Key": "confirm-key"}, json={"order_id": order_id, "confirmed_by": "customer"})
        replay = client.post("/api/v1/checkout/confirm", headers={**headers, "Idempotency-Key": "confirm-key"}, json={"order_id": order_id, "confirmed_by": "customer"})

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert create_order.call_count == 1


def test_refund_replay_calls_razorpay_once_and_state_waits_for_webhook(test_db):
    client = TestClient(app)
    customer_id, headers = customer_session(client, "refund-idempotent@example.com")
    add_cart_item(client, customer_id, headers)

    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_refund_order"}):
        checkout = client.post("/api/v1/checkout/initiate", headers=headers, json={"customer_id": customer_id})
    order_id = checkout.json()["order_id"]

    async def mark_paid():
        async with test_db() as session:
            order = await session.get(Order, order_id)
            order.status = OrderStatus.PAID
            session.add(Payment(order_id=order_id, razorpay_payment_id="pay_refund_1", status=PaymentStatus.CAPTURED, amount_paise=2500))
            await session.commit()

    asyncio.run(mark_paid())
    with patch("backend.services.payment_service.create_refund", return_value={"id": "rfnd_1", "status": "processed"}) as create_refund:
        first = client.post("/api/v1/orders/{}/refund".format(order_id), headers={**headers, "Idempotency-Key": "refund-key"}, json={"amount_paise": 1000, "reason": "changed mind"})
        replay = client.post("/api/v1/orders/{}/refund".format(order_id), headers={**headers, "Idempotency-Key": "refund-key"}, json={"amount_paise": 1000, "reason": "changed mind"})

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert create_refund.call_count == 1
    conflict = client.post("/api/v1/orders/{}/refund".format(order_id), headers={**headers, "Idempotency-Key": "refund-key"}, json={"amount_paise": 900, "reason": "changed mind"})
    assert conflict.status_code == 409

    async def read_status():
        async with test_db() as session:
            return (await session.get(Order, order_id)).status

    assert asyncio.run(read_status()) == OrderStatus.PAID


def test_cancellation_replay_is_safe():
    client = TestClient(app)
    customer_id, headers = customer_session(client, "cancel-idempotent@example.com")
    add_cart_item(client, customer_id, headers)
    with patch("backend.services.checkout_service.create_order", return_value={"id": "rp_cancel_order"}):
        checkout = client.post("/api/v1/checkout/initiate", headers=headers, json={"customer_id": customer_id})
    order_id = checkout.json()["order_id"]

    first = client.post(f"/api/v1/orders/{order_id}/cancel", headers={**headers, "Idempotency-Key": "cancel-key"}, json={"reason": "duplicate-safe"})
    replay = client.post(f"/api/v1/orders/{order_id}/cancel", headers={**headers, "Idempotency-Key": "cancel-key"}, json={"reason": "duplicate-safe"})
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"


def test_failed_checkout_is_replayed_as_failure_not_success():
    client = TestClient(app)
    customer_id, headers = customer_session(client, "checkout-failure@example.com")
    add_cart_item(client, customer_id, headers)
    with patch("backend.services.checkout_service.create_order", side_effect=RuntimeError("provider unavailable")) as create_order:
        first = client.post("/api/v1/checkout/initiate", headers={**headers, "Idempotency-Key": "failed-key"}, json={"customer_id": customer_id})
        replay = client.post("/api/v1/checkout/initiate", headers={**headers, "Idempotency-Key": "failed-key"}, json={"customer_id": customer_id})

    assert first.status_code == 502
    assert replay.status_code == 502
    assert replay.headers["Idempotent-Replay"] == "true"
    assert create_order.call_count == 1