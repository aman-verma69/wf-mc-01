"""
Thin wrapper around Razorpay's official Python SDK.

Requires: pip install razorpay
Requires env vars: RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
(https://dashboard.razorpay.com/app/keys)

This module ONLY talks to Razorpay. No business logic, no policy checks —
those live in services/ and policy/. Keeping this thin makes it trivial
to mock in tests (see tests/integration/test_razorpay_client.py).
"""
import razorpay

from backend.config.settings import get_settings

settings = get_settings()

_client: razorpay.Client | None = None


def get_client() -> razorpay.Client:
    global _client
    if _client is None:
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError(
                "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set. "
                "Add them to your .env file — see .env.example."
            )
        _client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    return _client


def create_order(amount_paise: int, currency: str = "INR", receipt: str | None = None, notes: dict | None = None) -> dict:
    """Creates a Razorpay Order. amount_paise MUST be an integer in the
    smallest currency unit (paise for INR) — never pass rupees as a float.
    """
    client = get_client()
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "payment_capture": 1,  # auto-capture; Verification service still confirms via webhook
    }
    if receipt:
        payload["receipt"] = receipt
    if notes:
        payload["notes"] = notes
    return client.order.create(data=payload)


def fetch_payment(razorpay_payment_id: str) -> dict:
    return get_client().payment.fetch(razorpay_payment_id)


def create_refund(razorpay_payment_id: str, amount_paise: int | None = None, notes: dict | None = None) -> dict:
    """Full refund if amount_paise is None, partial otherwise."""
    payload: dict = {}
    if amount_paise is not None:
        payload["amount"] = amount_paise
    if notes:
        payload["notes"] = notes
    return get_client().payment.refund(razorpay_payment_id, payload)


def fetch_dispute(razorpay_dispute_id: str) -> dict:
    return get_client().dispute.fetch(razorpay_dispute_id)


def submit_dispute_evidence(razorpay_dispute_id: str, evidence: dict) -> dict:
    return get_client().dispute.contest(razorpay_dispute_id, evidence)
