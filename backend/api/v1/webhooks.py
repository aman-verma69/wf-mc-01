"""
Razorpay webhook receiver. Register this URL (POST /api/v1/webhooks/razorpay)
in the Razorpay dashboard under Settings > Webhooks, subscribed to:
  payment.captured, payment.failed, refund.processed,
  dispute.created, dispute.won, dispute.lost

The signature is verified BEFORE the body is parsed or touched — see
integrations/razorpay/webhooks.py. Heavy processing is handed off to
workers/webhook_worker.py so this endpoint returns fast (Razorpay retries
on slow/failed responses).
"""
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.integrations.razorpay.webhooks import InvalidWebhookSignature, parse_event, verify_signature
from backend.services.dispute_service import handle_dispute_created, handle_dispute_resolved
from backend.services.payment_service import handle_payment_captured, handle_payment_failed, handle_refund_processed

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    try:
        verify_signature(raw_body, x_razorpay_signature)
    except InvalidWebhookSignature:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(raw_body)
    event, entity = parse_event(payload)

    handlers = {
        "payment.captured": lambda: handle_payment_captured(db, entity),
        "payment.failed": lambda: handle_payment_failed(db, entity),
        "refund.processed": lambda: handle_refund_processed(db, entity),
        "dispute.created": lambda: handle_dispute_created(db, entity),
        "dispute.won": lambda: handle_dispute_resolved(db, entity, won=True),
        "dispute.lost": lambda: handle_dispute_resolved(db, entity, won=False),
    }

    handler = handlers.get(event)
    if handler:
        await handler()

    # Always 200 on a verified signature, even for events we don't act on —
    # Razorpay will keep retrying otherwise.
    return {"status": "ok", "event": event}
