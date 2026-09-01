# AI Commerce Platform

Agentic commerce on top of Razorpay. See `docs/architecture.md` for the
full design (agentic layer → guardrail gate → deterministic services).

## Setup

```bash
cp .env.example .env
# fill in the keys below, then:
pip install -r requirements.txt
python -m scripts.seed_db          # creates tables
uvicorn backend.main:app --reload  # or: docker-compose up
```

## API keys you need to add (in `.env`)

| Key | Where it's used | Get it from |
|---|---|---|
| `RAZORPAY_KEY_ID` | `backend/integrations/razorpay/client.py` — Orders, Payments, Refunds, Disputes | https://dashboard.razorpay.com/app/keys |
| `RAZORPAY_KEY_SECRET` | same as above | same |
| `RAZORPAY_WEBHOOK_SECRET` | `backend/integrations/razorpay/webhooks.py` — verifies every incoming webhook at `POST /api/v1/webhooks/razorpay` | Razorpay Dashboard → Settings → Webhooks → set secret when you register the URL |
| `XAI_API_KEY` | `backend/integrations/llm/grok_client.py` — used by `buyer_agent`, `customer_agent`, `growth_agent` | https://console.x.ai |
| `GPT_OSS_BASE_URL` / `GPT_OSS_API_KEY` | `backend/integrations/llm/gpt_oss_client.py` — used by `catalog_agent`, `analytics_agent`, `campaign_agent`. **This is self-hosted** (Ollama/vLLM) — there's no hosted key from a provider, point the URL at your own server | run `ollama pull gpt-oss:20b && ollama serve`, or `vllm serve openai/gpt-oss-20b` |
| `TAVILY_API_KEY` | `backend/integrations/tavily/client.py` — web search tool used by `catalog_agent` / `growth_agent` | https://app.tavily.com |
| `DATABASE_URL` | `backend/database/session.py` | your Postgres instance |
| `JWT_SECRET_KEY` | `backend/auth/security.py` | a random secret of at least 32 bytes |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `backend/auth/security.py` | access-token lifetime (default: 60) |
| `SMTP_*` / `WHATSAPP_API_KEY` | `backend/services/notification_service.py` (currently stubbed with `logger.info` — wire up a real provider when ready) | your email/WhatsApp provider |

## Razorpay webhook setup (do this once you have a public URL)

1. Dashboard → Settings → Webhooks → Add New Webhook
2. URL: `https://<your-domain>/api/v1/webhooks/razorpay`
3. Secret: generate one, put it in `RAZORPAY_WEBHOOK_SECRET`
4. Subscribe to at least: `payment.captured`, `payment.failed`,
   `refund.processed`, `dispute.created`, `dispute.won`, `dispute.lost`

## What's implemented vs stubbed

**Fully implemented (critical path):**
- Guardrail gate (delegation scope + spend limit → allow/block/escalate)
- Checkout service (Razorpay Order creation, human-confirmation flow)
- Payment service (webhook-driven, idempotent, refunds)
- Dispute service (full lifecycle)
- Webhook signature verification
- Audit logging on every decision
- Agent tool-calling loop (Groq + gpt-oss-20B backends)
- Tavily search tool

**Stubbed — needs your product/business logic:**
- `notification_service.py` — logs instead of sending real email/WhatsApp
- `workers/scheduled_jobs.py::run_abandoned_cart_sweep` — no cart persistence model yet
- `frontend/` — directory structure only, no components built
- Catalog/product data model — not defined; agents assume you'll wire this in
- `database/migrations/` — using `create_all` for dev; add Alembic for production

## Testing

```bash
pytest tests/
```

`tests/integration/` should mock Razorpay calls (don't hit the live API
in CI) — record fixtures for webhook payloads rather than calling out.

## Customer authentication

Register and log in through `POST /api/v1/auth/register` and
`POST /api/v1/auth/login`. Send the returned bearer token as
`Authorization: Bearer <access_token>` to call `/auth/me`, cart, checkout,
agent, and order routes. Customer identity is taken from the verified JWT;
legacy `customer_id` path/body fields are retained only for route compatibility
and must match the authenticated customer.
