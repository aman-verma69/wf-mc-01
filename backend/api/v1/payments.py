from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.schemas.api_schemas import RefundRequest
from backend.services.payment_service import refund_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/refund")
async def refund(request: RefundRequest, db: AsyncSession = Depends(get_db)):
    result = await refund_payment(
        db, actor="api", razorpay_payment_id=request.razorpay_payment_id,
        amount_paise=request.amount_paise, reason=request.reason,
    )
    return result
