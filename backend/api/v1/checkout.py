from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer
from backend.database.models import Customer, Order
from backend.database.session import get_db
from backend.schemas.api_schemas import CheckoutInitiateRequest, CheckoutInitiateResponse, ConfirmCheckoutRequest
from backend.services.cart_service import get_cart
from backend.services.checkout_service import CheckoutAwaitingConfirmation, CheckoutBlocked, confirm_and_create_order, initiate_checkout

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/initiate", response_model=CheckoutInitiateResponse)
async def initiate(request: CheckoutInitiateRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    cart = await get_cart(db, customer_id=customer.id)
    if not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    try:
        order = await initiate_checkout(
            db,
            actor=request.actor,
            customer_id=customer.id,
            cart_snapshot=cart,
            delegation_scope=["checkout"],
        )
    except CheckoutBlocked as exc:
        raise HTTPException(status_code=403, detail=exc.reason) from exc
    except CheckoutAwaitingConfirmation as exc:
        raise HTTPException(status_code=202, detail={"order_id": exc.order_id, "reason": exc.reason, "status": "awaiting_confirmation"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CheckoutInitiateResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        amount_paise=order.amount_paise,
        currency=order.currency,
        status=order.status.value,
        razorpay_order_id=order.razorpay_order_id,
    )


@router.post("/confirm")
async def confirm(request: ConfirmCheckoutRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    """Called when a human (merchant dashboard / buyer app) approves a
    checkout that the guardrail escalated for exceeding the autonomous
    spend limit.
    """
    pending_order = await db.get(Order, request.order_id)
    if pending_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if pending_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    try:
        order = await confirm_and_create_order(db, request.order_id, request.confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"order_id": order.id, "razorpay_order_id": order.razorpay_order_id, "status": order.status.value}
