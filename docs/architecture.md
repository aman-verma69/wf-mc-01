# Architecture

## Layers

```
LlamaIndex Workflow (backend/workflows/commerce_workflow.py)
   │
   ├── Agentic layer (backend/agents/) — LLM reasoning, Grok or gpt-oss-20B
   │     buyer · catalog · customer · analytics · growth · campaign
   │
   ├── Guardrail gate (backend/policy/guardrail.py) — hard chokepoint,
   │     no LLM calls, rule-based only. Every checkout/payment request
   │     from an agent passes through here first.
   │
   └── Deterministic services (backend/services/) — no LLM calls, ever
         checkout · payment · dispute · notification
```

## tools/ vs services/ — the boundary that matters

- `backend/tools/` = **LLM-callable wrappers**. Thin. Validate shape,
  call a service, return a JSON-serializable result. No business logic.
- `backend/services/` = **actual business logic**. Guardrail checks,
  Razorpay calls, DB writes, idempotency. This is where correctness lives.

If you're adding a feature and unsure where code goes: if it decides
whether something is *allowed*, it's `policy/`. If it decides *what
happens* once allowed, it's `services/`. If it's just exposing that to
an LLM, it's `tools/`.

## Payment flow

1. Buyer agent (only agent with `checkout` in its delegation scope) calls
   the `initiate_checkout` tool.
2. `services/checkout_service.py` calls `policy/guardrail.py` first.
   - Blocked → agent gets a reason, no order created.
   - Escalated → order created in `AWAITING_CONFIRMATION`, a human must
     hit `POST /api/v1/checkout/confirm` before Razorpay is touched.
   - Allowed → Razorpay Order created immediately.
3. Frontend/customer completes payment via Razorpay Checkout using the
   `razorpay_order_id`.
4. **Razorpay webhook** (`payment.captured`) is the only thing that marks
   an order PAID — never the client-side success callback.
5. Notification service fires on payment confirmation. Never composed
   ad hoc by an agent.

## Disputes

Chargebacks arrive via `dispute.created` webhook, get their own row and
status lifecycle (`OPEN → EVIDENCE_SUBMITTED → WON/LOST`), independent
of the payment/order lifecycle. See `services/dispute_service.py`.

## Audit

Every guardrail decision (allowed/blocked/escalated) and every
state-changing service call writes to `audit_log`, even on the happy
path. See `backend/audit/audit_logger.py`.
