# Security notes

## Secrets

All secrets are read exclusively via `backend/config/settings.py`
(pydantic-settings, loads from `.env`). Never call `os.getenv()` directly
elsewhere in the codebase — it makes secrets impossible to audit.

`.env` is gitignored. Only `.env.example` (no real values) is committed.

## Webhook verification

`backend/integrations/razorpay/webhooks.py::verify_signature` runs a
constant-time HMAC-SHA256 comparison against `RAZORPAY_WEBHOOK_SECRET`
**before** the raw body is parsed as JSON or touches the database. Any
request with a missing/invalid `X-Razorpay-Signature` header is rejected
with 400 before any handler runs.

## Idempotency

Razorpay may deliver the same webhook more than once. `payment_service.py`
checks for an existing `Payment` row by `razorpay_payment_id` before
writing — reprocessing a duplicate webhook is a no-op, not a duplicate
charge or duplicate notification.

## Guardrail

`backend/policy/guardrail.py` is the only place that decides whether an
agent-initiated payment proceeds. It is deliberately free of LLM calls.
Two checks ship by default:

- **Delegation scope** — only agents with `"checkout"` in their scope
  can trigger a checkout at all (currently: `buyer_agent` only).
- **Spend limit** — `MAX_AUTONOMOUS_SPEND_PAISE` in `.env`. Above it,
  the order is parked in `AWAITING_CONFIRMATION` and a human must approve
  via `POST /api/v1/checkout/confirm`.

Add further checks (velocity limits, blocked customers, geography) as
additional functions in the `checks` list inside `check_checkout_request`.

## Amounts

Every amount in the system is an integer in **paise** (INR's smallest
unit), never a float in rupees. Floats introduce rounding errors that
compound at scale; always convert at the UI boundary only.
