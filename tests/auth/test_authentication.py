import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings
from backend.database.models import Base
from backend.database.session import get_db
from backend.main import app
from backend.workflows.commerce_workflow import CommerceWorkflow


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
    yield
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "correct horse battery"})
    assert registered.status_code == 201, registered.text
    customer_id = registered.json()["id"]
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "correct horse battery"})
    return customer_id, logged_in.json()["access_token"]


def test_registration_login_and_me():
    client = TestClient(app)
    customer_id, token = register_and_login(client, "alice@example.com")

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == customer_id
    assert "password_hash" not in me.json()


def test_duplicate_registration_and_wrong_password_are_rejected():
    client = TestClient(app)
    register_and_login(client, "duplicate@example.com")

    duplicate = client.post("/api/v1/auth/register", json={"email": "duplicate@example.com", "password": "another password"})
    assert duplicate.status_code == 409

    wrong_password = client.post("/api/v1/auth/login", json={"email": "duplicate@example.com", "password": "wrong password"})
    assert wrong_password.status_code == 401


def test_auth_rejects_missing_invalid_and_expired_tokens():
    client = TestClient(app)
    customer_id, _ = register_and_login(client, "token@example.com")

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401

    expired = jwt.encode(
        {"sub": customer_id, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        get_settings().JWT_SECRET_KEY,
        algorithm=get_settings().JWT_ALGORITHM,
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_customers_cannot_access_each_others_cart_or_orders():
    client = TestClient(app)
    customer_a, token_a = register_and_login(client, "a@example.com")
    customer_b, token_b = register_and_login(client, "b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    add = client.post(
        f"/api/v1/customers/{customer_a}/cart/items",
        headers=headers_a,
        json={"product_id": "prod-1", "name": "Headphones", "quantity": 1, "unit_price_paise": 2500},
    )
    assert add.status_code == 200

    assert client.get(f"/api/v1/customers/{customer_a}/cart", headers=headers_b).status_code == 403
    assert client.patch(f"/api/v1/customers/{customer_a}/cart/items/prod-1", headers=headers_b, json={"quantity": 2}).status_code == 403

    checkout = client.post(f"/api/v1/checkout/initiate", headers=headers_a, json={"customer_id": customer_a})
    assert checkout.status_code == 200
    order_id = checkout.json()["order_id"]

    assert client.get(f"/api/v1/customers/{customer_a}/orders", headers=headers_b).status_code == 403
    assert client.get(f"/api/v1/orders/{order_id}", headers=headers_b).status_code == 403
    assert client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers_b, json={"reason": "test"}).status_code == 403
    assert client.post(f"/api/v1/orders/{order_id}/refund", headers=headers_b, json={"reason": "test"}).status_code == 403


def test_agent_chat_uses_authenticated_customer_identity(monkeypatch):
    captured = {}

    async def fake_run(self, *, db, message, agent_key=None, customer_id=None):
        captured["customer_id"] = customer_id
        return {"agent": "buyer_agent", "reply": "ok", "products": [], "ok": True, "error": None}

    client = TestClient(app)
    customer_id, token = register_and_login(client, "agent@example.com")
    monkeypatch.setattr(CommerceWorkflow, "run", fake_run)

    response = client.post(
        "/api/v1/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What's in my cart?", "customer_id": "another-customer"},
    )

    assert response.status_code == 200
    assert captured["customer_id"] == customer_id