from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.database.models import Order, OrderStatus, Payment
from backend.services.payment_service import refund_payment


async def get_order_by_id(db: AsyncSession, *, order_id: str) -> Order | None:
    return await db.get(Order, order_id)


async def get_customer_orders(db: AsyncSession, *, customer_id: str, order_id: str | None = None) -> list[dict[str, Any]]:
    if not customer_id:
        return []

    query = select(Order).where(Order.customer_id == customer_id)
    if order_id:
        query = query.where(Order.id == order_id)
    query = query.order_by(Order.created_at.desc())
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "status": order.status.value,
            "amount_paise": order.amount_paise,
            "currency": order.currency,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "razorpay_order_id": order.razorpay_order_id,
            "cart_snapshot": order.cart_snapshot,
        }
        for order in rows
    ]


async def get_order_status_snapshot(db: AsyncSession, *, customer_id: str, order_id: str | None = None) -> dict[str, Any]:
    orders = await get_customer_orders(db, customer_id=customer_id, order_id=order_id)
    if not orders:
        return {"orders": [], "order_id": order_id, "status": "not_found"}

    order = orders[0]
    payment = await db.scalar(select(Payment).where(Payment.order_id == order["order_id"]).order_by(Payment.created_at.desc()))
    payment_status = payment.status.value if payment else "not_started"
    return {
        "order_id": order["order_id"],
        "customer_id": customer_id,
        "status": order["status"],
        "payment_status": payment_status,
        "amount_paise": order["amount_paise"],
        "currency": order["currency"],
        "cart_snapshot": order["cart_snapshot"],
        "orders": orders,
    }


async def cancel_order(db: AsyncSession, *, actor: str, customer_id: str, order_id: str, reason: str = "customer_request") -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.customer_id != customer_id:
        raise PermissionError("Order does not belong to this customer")
    if order.status in {OrderStatus.REFUNDED, OrderStatus.CANCELLED}:
        raise ValueError(f"Order {order_id} is already {order.status.value}")
    if order.status == OrderStatus.PAID:
        raise ValueError("Paid orders require refund authorization and separate refund flow")

    order.status = OrderStatus.CANCELLED
    await db.commit()
    await db.refresh(order)
    await log_action(
        db,
        actor=actor,
        action="order.cancelled",
        decision="allowed",
        reason=reason,
        context={"order_id": order.id, "customer_id": customer_id},
    )
    return order


async def request_refund(db: AsyncSession, *, actor: str, customer_id: str, order_id: str, amount_paise: int | None = None, reason: str = "customer_request") -> dict[str, Any]:
    order = await db.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.customer_id != customer_id:
        raise PermissionError("Order does not belong to this customer")
    if order.status != OrderStatus.PAID:
        raise ValueError(f"Order {order_id} is not paid and cannot be refunded")

    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc()))
    if payment is None or payment.razorpay_payment_id is None:
        raise ValueError(f"Order {order_id} has no captured payment to refund")

    refund_result = await refund_payment(
        db,
        actor=actor,
        razorpay_payment_id=payment.razorpay_payment_id,
        amount_paise=amount_paise,
        reason=reason,
    )
    return {
        "order_id": order.id,
        "payment_id": payment.razorpay_payment_id,
        "status": "refund_requested",
        "refund": refund_result,
    }
