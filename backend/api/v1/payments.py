from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Order, Payment
from backend.database.session import get_db
from backend.schemas.api_schemas import RefundRequest
from backend.services.order_service import request_refund
from backend.services.payment_service import refund_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/refund")
async def refund(request: RefundRequest, db: AsyncSession = Depends(get_db)):
    if request.order_id:
        order = await db.get(Order, request.order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if request.customer_id and order.customer_id != request.customer_id:
            raise HTTPException(status_code=403, detail="Customer does not own this order")
        result = await request_refund(
            db,
            actor="api",
            customer_id=order.customer_id,
            order_id=request.order_id,
            amount_paise=request.amount_paise,
            reason=request.reason,
        )
        return result

    if not request.razorpay_payment_id:
        raise HTTPException(status_code=400, detail="razorpay_payment_id or order_id is required")

    payment = await db.scalar(select(Payment).where(Payment.razorpay_payment_id == request.razorpay_payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = await db.get(Order, payment.order_id)
    if request.customer_id and order is not None and order.customer_id != request.customer_id:
        raise HTTPException(status_code=403, detail="Customer does not own this payment")

    result = await refund_payment(
        db, actor="api", razorpay_payment_id=request.razorpay_payment_id,
        amount_paise=request.amount_paise, reason=request.reason,
    )
    return result
