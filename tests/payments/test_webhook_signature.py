import hashlib
import hmac

import pytest

from backend.integrations.razorpay import webhooks


def test_valid_signature_passes(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "RAZORPAY_WEBHOOK_SECRET", "test-secret")
    body = b'{"event": "payment.captured"}'
    sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    webhooks.verify_signature(body, sig)  # should not raise


def test_invalid_signature_raises(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "RAZORPAY_WEBHOOK_SECRET", "test-secret")
    body = b'{"event": "payment.captured"}'
    with pytest.raises(webhooks.InvalidWebhookSignature):
        webhooks.verify_signature(body, "wrong-signature")


def test_parse_event_extracts_entity():
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_123", "amount": 10000}}},
    }
    event, entity = webhooks.parse_event(payload)
    assert event == "payment.captured"
    assert entity["id"] == "pay_123"
