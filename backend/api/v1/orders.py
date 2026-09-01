from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer
from backend.database.models import Customer
from backend.database.models import Order
from backend.database.session import get_db
from backend.schemas.api_schemas import CancelOrderRequest, OrderStatusResponse
from backend.services.order_service import cancel_order, get_customer_orders, request_refund

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}", response_model=OrderStatusResponse)
async def get_order_status(order_id: str, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    return OrderStatusResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        amount_paise=order.amount_paise,
        currency=order.currency,
        cart_snapshot=order.cart_snapshot,
        razorpay_order_id=order.razorpay_order_id,
    )


@router.post("/{order_id}/cancel", response_model=OrderStatusResponse)
async def cancel_order_route(order_id: str, request: CancelOrderRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    existing_order = await db.get(Order, order_id)
    if existing_order is not None and existing_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    try:
        order = await cancel_order(db, actor="api", customer_id=customer.id, order_id=order_id, reason=request.reason)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OrderStatusResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        amount_paise=order.amount_paise,
        currency=order.currency,
        cart_snapshot=order.cart_snapshot,
        razorpay_order_id=order.razorpay_order_id,
    )


@router.post("/{order_id}/refund", response_model=dict)
async def refund_order_route(order_id: str, request: CancelOrderRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    existing_order = await db.get(Order, order_id)
    if existing_order is not None and existing_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    try:
        result = await request_refund(
            db,
            actor="api",
            customer_id=customer.id,
            order_id=order_id,
            reason=request.reason,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
