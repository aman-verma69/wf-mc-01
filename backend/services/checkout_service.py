"""
Deterministic checkout logic. No LLM calls anywhere in this file.
Every entrypoint here MUST go through the guardrail first if it was
triggered by an agent (see policy/guardrail.py).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.database.models import Order, OrderStatus, gen_uuid
from backend.integrations.razorpay.client import create_order
from backend.policy.guardrail import CheckoutRequest, GateDecision, check_checkout_request
from backend.services.cart_service import calculate_cart_total_paise, get_cart
from backend.services.catalog_service import reserve_order_inventory


class CheckoutBlocked(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class CheckoutAwaitingConfirmation(Exception):
    """Raised when the guardrail escalates — caller should surface a
    confirmation prompt to a human and retry via confirm_and_create_order."""
    def __init__(self, order_id: str, reason: str):
        self.order_id = order_id
        self.reason = reason
        super().__init__(reason)


async def initiate_checkout(
    db: AsyncSession,
    *,
    actor: str,
    customer_id: str,
    amount_paise: int | None = None,
    cart_snapshot: dict | None = None,
    delegation_scope: list[str] | None = None,
) -> Order:
    """Entry point for agent-driven checkout.

    The amount charged is derived from the trusted backend cart state rather than
    from any model-supplied value. If a caller provides a value, it is ignored for
    the final charge calculation.
    """
    normalized_cart = await get_cart(db, customer_id=customer_id)
    trusted_total = calculate_cart_total_paise(normalized_cart)
    if trusted_total <= 0:
        raise ValueError("Cart is empty or does not contain trusted product totals")

    gate_amount = int(trusted_total)
    gate_result = await check_checkout_request(
        db,
        CheckoutRequest(
            actor=actor,
            customer_id=customer_id,
            amount_paise=gate_amount,
            delegation_scope=delegation_scope,
        ),
    )

    if gate_result.decision == GateDecision.BLOCKED:
        raise CheckoutBlocked(gate_result.reason)

    if gate_result.decision == GateDecision.ESCALATED:
        order = await _create_pending_order(db, actor=actor, customer_id=customer_id, amount_paise=gate_amount, cart=normalized_cart)
        raise CheckoutAwaitingConfirmation(order.id, gate_result.reason)

    return await _create_order(db, actor=actor, customer_id=customer_id, amount_paise=gate_amount, cart_snapshot=normalized_cart)


async def confirm_and_create_order(db: AsyncSession, order_id: str, confirmed_by: str) -> Order:
    """Called when a human approves an escalated checkout. Creates the
    actual Razorpay order for a previously-parked Order row.
    """
    order = await db.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.status != OrderStatus.AWAITING_CONFIRMATION:
        raise ValueError(f"Order {order_id} is not awaiting confirmation (status={order.status})")

    rp_order = create_order(amount_paise=order.amount_paise, receipt=order.id)
    order.razorpay_order_id = rp_order["id"]
    order.status = OrderStatus.CREATED
    await db.commit()
    await db.refresh(order)

    await log_action(
        db,
        actor=f"human:{confirmed_by}",
        action="checkout.confirm",
        decision="allowed",
        context={"order_id": order.id, "amount_paise": order.amount_paise},
    )
    return order


async def _create_order(db: AsyncSession, *, actor: str, customer_id: str, amount_paise: int, cart_snapshot: dict) -> Order:
    order = await _create_pending_order(db, actor=actor, customer_id=customer_id, amount_paise=amount_paise, cart=cart_snapshot, status=OrderStatus.CREATED)
    try:
        rp_order = create_order(amount_paise=order.amount_paise)
    except Exception:
        from backend.services.catalog_service import release_order_inventory
        await release_order_inventory(db, order_id=order.id)
        order.status = OrderStatus.FAILED
        await db.commit()
        raise

    order.razorpay_order_id = rp_order["id"]
    await db.commit()
    await db.refresh(order)

    await log_action(
        db,
        actor=actor,
        action="checkout.initiate",
        decision="allowed",
        context={"order_id": order.id, "razorpay_order_id": rp_order["id"], "amount_paise": order.amount_paise},
    )
    return order


async def _create_pending_order(db: AsyncSession, *, actor: str, customer_id: str, amount_paise: int, cart: dict, status: OrderStatus = OrderStatus.AWAITING_CONFIRMATION) -> Order:
    order = Order(
        id=gen_uuid(),
        customer_id=customer_id,
        amount_paise=amount_paise,
        cart_snapshot={},
        created_by_agent=actor,
        status=status,
    )
    db.add(order)
    await db.flush()
    order.cart_snapshot = await reserve_order_inventory(db, order_id=order.id, cart=cart)
    order.amount_paise = calculate_cart_total_paise(order.cart_snapshot)
    await db.commit()
    await db.refresh(order)
    return order
