from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer
from backend.database.models import Customer, Order
from backend.database.session import get_db
from backend.schemas.api_schemas import CheckoutInitiateRequest, CheckoutInitiateResponse, ConfirmCheckoutRequest
from backend.services.cart_service import get_cart
from backend.services.checkout_service import CheckoutAwaitingConfirmation, CheckoutBlocked, confirm_and_create_order, initiate_checkout
from backend.services.idempotency_service import IdempotencyConflict, IdempotencyInProgress, complete, replay_body, reserve

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/initiate", response_model=CheckoutInitiateResponse)
async def initiate(request: CheckoutInitiateRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if request.customer_id is not None and request.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Customer identity does not match token")
    cart = await get_cart(db, customer_id=customer.id)
    if not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    record = None
    if idempotency_key is not None:
        try:
            record = await reserve(db, key=idempotency_key, operation="checkout.initiate", customer_id=customer.id, payload={"actor": request.actor, "customer_id": customer.id})
        except (ValueError, IdempotencyConflict) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, IdempotencyConflict) else 400, detail=str(exc)) from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc), headers={"Retry-After": "1"}) from exc
        replay = replay_body(record)
        if replay is not None:
            return JSONResponse(status_code=replay[0], content=replay[1], headers={"Idempotent-Replay": "true"})

    try:
        order = await initiate_checkout(
            db,
            actor=request.actor,
            customer_id=customer.id,
            cart_snapshot=cart,
            delegation_scope=["checkout"],
        )
    except CheckoutBlocked as exc:
        if record is not None:
            await complete(db, record, response_status=403, response_body={"detail": exc.reason}, status="failed")
        raise HTTPException(status_code=403, detail=exc.reason) from exc
    except CheckoutAwaitingConfirmation as exc:
        body = {"order_id": exc.order_id, "reason": exc.reason, "status": "awaiting_confirmation"}
        if record is not None:
            await complete(db, record, response_status=202, response_body={"detail": body}, resource_id=exc.order_id)
        raise HTTPException(status_code=202, detail=body) from exc
    except ValueError as exc:
        if record is not None:
            await complete(db, record, response_status=400, response_body={"detail": str(exc)}, status="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if record is not None:
            await complete(db, record, response_status=502, response_body={"detail": "Checkout provider is temporarily unavailable"}, status="failed")
        raise HTTPException(status_code=502, detail="Checkout provider is temporarily unavailable") from exc

    response_body = CheckoutInitiateResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        amount_paise=order.amount_paise,
        currency=order.currency,
        status=order.status.value,
        razorpay_order_id=order.razorpay_order_id,
    ).model_dump(mode="json")
    if record is not None:
        await complete(db, record, response_status=200, response_body=response_body, resource_id=order.id)
    return CheckoutInitiateResponse(**response_body)


@router.post("/confirm")
async def confirm(request: ConfirmCheckoutRequest, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    """Called when a human (merchant dashboard / buyer app) approves a
    checkout that the guardrail escalated for exceeding the autonomous
    spend limit.
    """
    pending_order = await db.get(Order, request.order_id)
    if pending_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if pending_order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Order does not belong to this customer")
    record = None
    if idempotency_key is not None:
        try:
            record = await reserve(db, key=idempotency_key, operation="checkout.confirm", customer_id=customer.id, payload={"order_id": request.order_id, "confirmed_by": request.confirmed_by})
        except (ValueError, IdempotencyConflict) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, IdempotencyConflict) else 400, detail=str(exc)) from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc), headers={"Retry-After": "1"}) from exc
        replay = replay_body(record)
        if replay is not None:
            return JSONResponse(status_code=replay[0], content=replay[1], headers={"Idempotent-Replay": "true"})
    try:
        order = await confirm_and_create_order(db, request.order_id, request.confirmed_by)
    except ValueError as e:
        if record is not None:
            await complete(db, record, response_status=400, response_body={"detail": str(e)}, status="failed")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        if record is not None:
            await complete(db, record, response_status=502, response_body={"detail": "Checkout provider is temporarily unavailable"}, status="failed")
        raise HTTPException(status_code=502, detail="Checkout provider is temporarily unavailable") from exc
    response_body = {"order_id": order.id, "razorpay_order_id": order.razorpay_order_id, "status": order.status.value}
    if record is not None:
        await complete(db, record, response_status=200, response_body=response_body, resource_id=order.id)
    return response_body
