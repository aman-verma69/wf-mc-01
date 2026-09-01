# Security notes

## Secrets

All secrets are read exclusively via `backend/config/settings.py`
(pydantic-settings, loads from `.env`). Never call `os.getenv()` directly
elsewhere in the codebase — it makes secrets impossible to audit.

`.env` is gitignored. Only `.env.example` (no real values) is committed.

## Customer authentication

Customers authenticate with email and an Argon2 password hash. Passwords are
never returned or stored in plaintext. Login issues a signed JWT using
`JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` from
the central settings object. Protected commerce routes load the customer from
the token subject and reject missing, invalid, expired, or inactive identities.
Any legacy customer ID supplied in a path or body is checked against that
identity and cannot select another customer's cart or order.

## Idempotent commerce writes

`idempotency_records` stores the operation, authenticated customer, SHA-256
hash of non-secret request fields, processing state, response, and resource ID.
The key is globally unique, so it cannot be reused across operations or
customers. `checkout.initiate`, `checkout.confirm`, `order.cancel`, and
`order.refund` use this store when an `Idempotency-Key` header is supplied.
Completed and failed results replay without repeating external side effects;
processing requests return `409` with `Retry-After`; mismatched reuse returns
`409`. Records older than `IDEMPOTENCY_PROCESSING_TIMEOUT_SECONDS` become a
stored `409` recovery result instead of being retried automatically. Failed
provider calls are stored as failures and are never replayed as successes.
Razorpay webhook idempotency remains independent of this client header.

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
