from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.schemas.api_schemas import ConfirmCheckoutRequest
from backend.services.checkout_service import confirm_and_create_order

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/confirm")
async def confirm(request: ConfirmCheckoutRequest, db: AsyncSession = Depends(get_db)):
    """Called when a human (merchant dashboard / buyer app) approves a
    checkout that the guardrail escalated for exceeding the autonomous
    spend limit.
    """
    try:
        order = await confirm_and_create_order(db, request.order_id, request.confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"order_id": order.id, "razorpay_order_id": order.razorpay_order_id, "status": order.status.value}
