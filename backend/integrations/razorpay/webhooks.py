"""
Webhook signature verification. This is the security-critical boundary
between "the internet" and "our database" — never trust a webhook body
without passing it through verify_signature() first.

Register the webhook in the Razorpay dashboard (Settings > Webhooks),
pointed at POST /api/v1/webhooks/razorpay, subscribed to at least:
  payment.captured, payment.failed, refund.processed,
  dispute.created, dispute.won, dispute.lost

Requires env var: RAZORPAY_WEBHOOK_SECRET (set when you register the webhook)
"""
import hashlib
import hmac

from backend.config.settings import get_settings

settings = get_settings()


class InvalidWebhookSignature(Exception):
    pass


def verify_signature(raw_body: bytes, received_signature: str) -> None:
    """Raises InvalidWebhookSignature if the payload doesn't match.
    Call this BEFORE json.loads()-ing the body or touching the DB.
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET is not set — see .env.example.")

    expected = hmac.new(
        key=settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # constant-time compare — never use `==` for signatures
    if not hmac.compare_digest(expected, received_signature):
        raise InvalidWebhookSignature("Webhook signature mismatch")


def parse_event(payload: dict) -> tuple[str, dict]:
    """Returns (event_name, entity_payload), e.g. ("payment.captured", {...})."""
    event = payload.get("event", "unknown")
    entity_key = event.split(".")[0]  # "payment", "refund", "dispute"
    entity = payload.get("payload", {}).get(entity_key, {}).get("entity", {})
    return event, entity
