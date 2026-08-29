"""
The ONLY place in the codebase that sends outbound notifications.
Agents/services call these functions rather than composing messages
and sending them ad hoc — keeps templates, rate limiting, and channel
choice in one place.

Requires (optional, only if you want real delivery):
  SMTP_HOST / SMTP_USER / SMTP_PASSWORD  — email
  WHATSAPP_API_KEY                       — WhatsApp Business provider
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Dispute, Order

logger = logging.getLogger("notifications")


async def notify_order_paid(db: AsyncSession, order: Order) -> None:
    # TODO: wire to real email/SMS/WhatsApp provider using settings.SMTP_* / WHATSAPP_API_KEY
    logger.info("NOTIFY customer=%s order=%s amount_paise=%s: payment received",
                order.customer_id, order.id, order.amount_paise)


async def notify_dispute_opened(db: AsyncSession, dispute: Dispute) -> None:
    # TODO: wire to merchant-facing notification channel (email/Slack)
    logger.info("NOTIFY merchant: dispute opened, dispute_id=%s payment_id=%s",
                dispute.id, dispute.payment_id)


async def notify_abandoned_cart(db: AsyncSession, customer_id: str, cart_snapshot: dict) -> None:
    # TODO: wire to WhatsApp/email for cart-recovery nudges (used by Growth agent)
    logger.info("NOTIFY customer=%s: abandoned cart nudge, items=%s", customer_id, len(cart_snapshot.get("items", [])))
