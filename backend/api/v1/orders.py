from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer
from backend.database.models import Customer
from backend.database.models import Order
from backend.database.session import get_db
from backend.schemas.api_schemas import CancelOrderRequest, OrderStatusResponse, RefundRequest
from backend.services.order_service import cancel_order, get_customer_orders, request_refund
from backend.services.idempotency_service import IdempotencyConflict, IdempotencyInProgress, complete, replay_body, reserve

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
async def cancel_order_route(order_id: str, request: CancelOrderRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    existing_order = await db.get(Order, order_id)
    if existing_order is not None and existing_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    record = None
    if idempotency_key is not None:
        try:
            record = await reserve(db, key=idempotency_key, operation="order.cancel", customer_id=customer.id, payload={"order_id": order_id, "reason": request.reason})
        except (ValueError, IdempotencyConflict) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, IdempotencyConflict) else 400, detail=str(exc)) from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc), headers={"Retry-After": "1"}) from exc
        replay = replay_body(record)
        if replay is not None:
            return JSONResponse(status_code=replay[0], content=replay[1], headers={"Idempotent-Replay": "true"})
    try:
        order = await cancel_order(db, actor="api", customer_id=customer.id, order_id=order_id, reason=request.reason)
    except (ValueError, PermissionError) as exc:
        if record is not None:
            await complete(db, record, response_status=400, response_body={"detail": str(exc)}, status="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response_body = OrderStatusResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        amount_paise=order.amount_paise,
        currency=order.currency,
        cart_snapshot=order.cart_snapshot,
        razorpay_order_id=order.razorpay_order_id,
    ).model_dump(mode="json")
    if record is not None:
        await complete(db, record, response_status=200, response_body=response_body, resource_id=order.id)
    return OrderStatusResponse(**response_body)


@router.post("/{order_id}/refund", response_model=dict)
async def refund_order_route(order_id: str, request: RefundRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    existing_order = await db.get(Order, order_id)
    if existing_order is not None and existing_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    record = None
    if idempotency_key is not None:
        try:
            record = await reserve(db, key=idempotency_key, operation="order.refund", customer_id=customer.id, payload={"order_id": order_id, "amount_paise": request.amount_paise, "reason": request.reason})
        except (ValueError, IdempotencyConflict) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, IdempotencyConflict) else 400, detail=str(exc)) from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc), headers={"Retry-After": "1"}) from exc
        replay = replay_body(record)
        if replay is not None:
            return JSONResponse(status_code=replay[0], content=replay[1], headers={"Idempotent-Replay": "true"})
    try:
        result = await request_refund(
            db,
            actor="api",
            customer_id=customer.id,
            order_id=order_id,
            amount_paise=request.amount_paise,
            reason=request.reason,
        )
    except (ValueError, PermissionError) as exc:
        if record is not None:
            await complete(db, record, response_status=400, response_body={"detail": str(exc)}, status="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if record is not None:
            await complete(db, record, response_status=502, response_body={"detail": "Refund provider is temporarily unavailable"}, status="failed")
        raise HTTPException(status_code=502, detail="Refund provider is temporarily unavailable") from exc
    if record is not None:
        await complete(db, record, response_status=200, response_body=result, resource_id=order_id)
    return result
