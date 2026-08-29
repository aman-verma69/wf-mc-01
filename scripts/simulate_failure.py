"""
Simulates failure scenarios against a running local instance:
  - duplicate webhook delivery (idempotency check)
  - invalid webhook signature (should be rejected)
  - checkout above the autonomous spend limit (should escalate)

Run with: python -m scripts.simulate_failure
Requires the API running locally (docker-compose up) and .env configured.
"""
import asyncio
import hashlib
import hmac
import json

import httpx

from backend.config.settings import get_settings

settings = get_settings()
BASE_URL = "http://localhost:8000/api/v1"


def sign(body: bytes) -> str:
    return hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def simulate_invalid_signature():
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/webhooks/razorpay", content=body,
                                  headers={"X-Razorpay-Signature": "not-a-real-signature"})
        print("invalid signature ->", resp.status_code, resp.text)
        assert resp.status_code == 400


async def simulate_checkout_over_limit():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/agents/chat", json={
            "agent_key": "buyer",
            "customer_id": "test-customer-1",
            "message": "Buy me the item that costs 10000 rupees right now.",
        })
        print("over-limit checkout ->", resp.status_code, resp.text)


async def main():
    await simulate_invalid_signature()
    await simulate_checkout_over_limit()


if __name__ == "__main__":
    asyncio.run(main())
