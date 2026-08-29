"""
Payment state is driven by Razorpay WEBHOOKS, not client-side callbacks.
Never mark an order as paid just because the frontend says "payment done" —
wait for payment.captured to arrive here. This file is idempotent: the
same webhook can be delivered more than once by Razorpay and must be
safe to process twice.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.database.models import Order, OrderStatus, Payment, PaymentStatus
from backend.integrations.razorpay.client import create_refund


async def handle_payment_captured(db: AsyncSession, entity: dict) -> None:
    razorpay_payment_id = entity["id"]
    razorpay_order_id = entity["order_id"]
    amount_paise = entity["amount"]
    method = entity.get("method")

    # idempotency: if we've already recorded this payment, do nothing
    existing = await db.scalar(select(Payment).where(Payment.razorpay_payment_id == razorpay_payment_id))
    if existing is not None:
        return

    order = await db.scalar(select(Order).where(Order.razorpay_order_id == razorpay_order_id))
    if order is None:
        await log_action(db, actor="payment_service", action="payment.captured", decision="blocked",
                          reason="No matching local order for razorpay_order_id", context={"razorpay_order_id": razorpay_order_id})
        return

    payment = Payment(
        order_id=order.id,
        razorpay_payment_id=razorpay_payment_id,
        status=PaymentStatus.CAPTURED,
        amount_paise=amount_paise,
        method=method,
        raw_webhook_payload=entity,
    )
    db.add(payment)
    order.status = OrderStatus.PAID
    await db.commit()

    await log_action(db, actor="payment_service", action="payment.captured", decision="allowed",
                      context={"order_id": order.id, "razorpay_payment_id": razorpay_payment_id, "amount_paise": amount_paise})

    # Notify — see services/notification_service.py
    from backend.services.notification_service import notify_order_paid
    await notify_order_paid(db, order)


async def handle_payment_failed(db: AsyncSession, entity: dict) -> None:
    razorpay_order_id = entity.get("order_id")
    order = await db.scalar(select(Order).where(Order.razorpay_order_id == razorpay_order_id))
    if order is None:
        return

    order.status = OrderStatus.FAILED
    await db.commit()

    await log_action(db, actor="payment_service", action="payment.failed", decision="allowed",
                      context={"order_id": order.id, "error": entity.get("error_description")})


async def refund_payment(db: AsyncSession, *, actor: str, razorpay_payment_id: str, amount_paise: int | None = None, reason: str = "") -> dict:
    """Initiates a refund via Razorpay. The order status flips to REFUNDED
    only once refund.processed webhook confirms it — see handle_refund_processed.
    """
    result = create_refund(razorpay_payment_id, amount_paise=amount_paise, notes={"reason": reason})
    await log_action(db, actor=actor, action="payment.refund_initiated", decision="allowed",
                      context={"razorpay_payment_id": razorpay_payment_id, "amount_paise": amount_paise, "reason": reason})
    return result


async def handle_refund_processed(db: AsyncSession, entity: dict) -> None:
    razorpay_payment_id = entity.get("payment_id")
    payment = await db.scalar(select(Payment).where(Payment.razorpay_payment_id == razorpay_payment_id))
    if payment is None:
        return

    payment.status = PaymentStatus.REFUNDED
    order = await db.get(Order, payment.order_id)
    if order is not None:
        order.status = OrderStatus.REFUNDED
    await db.commit()

    await log_action(db, actor="payment_service", action="payment.refund_processed", decision="allowed",
                      context={"razorpay_payment_id": razorpay_payment_id})
